# Anne Happy Episode 1

# imports
import vapoursynth as vs
import atomchtools as att
import gradfun_amod as gfa
from adptvgrnMod import adptvgrnMod as agm
import adjust
import havsfunc as hvf
import lvsfunc as lvf
import kagefunc as kgf
import fvsfunc as fvf
import muvsfunc as muvf
import vardefunc as vdf
from vsutil import depth
from vsutil.clips import get_y

core = vs.core
core.max_cache_size = 11000  # set memory limit so it doesn't freeze everything lol
episode = '01'
end_frame = 34045  # trim black frames
op_start, op_end = 6546, 8701
ed_start, ed_end, nced_offset = 32376, 33610, 920
native_width, native_height = 1280, 720  # as returned by getnative and anibin
output_width, output_height = 1920, 1080
kernel = 'bicubic'  # ref only
b, c = 1/3, 1/3  # 0.2 0.5 possible but 1/3, 1/3 slighlty sharper & no issues identified
goframe = 32551  # black bars first frame


src = depth(lvf.src(r"Source/01.mkv", force_lsmas=True)[:end_frame+1], 16)
ncop = depth(lvf.src(r"Source/ncop.mkv", force_lsmas=True)
             [:op_end-op_start+1], 16)
nced = depth(lvf.src(r"Source/nced.mkv", force_lsmas=True)
             [nced_offset:nced_offset+ed_end-ed_start+1], 16)
mask_mappings = ['[31527 31598]', '[31611 31682]', '[31691 31759]', '[31791 31862]',
                 '[31875 31947]', '[32005 32092]', '[32105 32192]', '[32201 32268]', '[32278 32358]']
exclude_rescale = '[32545 32564]'


def image_to_clip(clip: vs.VideoNode, image: str):
    '''Imports the image, resizes to match the video format/fps then loops to cover the full video length for processing'''
    clipb = core.imwri.Read(image)
    clipb = core.std.AssumeFPS(clipb, fpsnum=clip.fps_num, fpsden=clip.fps_den)
    clipb = core.resize.Spline36(clipb, format=clip.format.id, matrix_s="709")
    clipb = core.std.Loop(clipb, end_frame-1)
    return clipb


def creditmask(clip: vs.VideoNode):
    '''Create a blank clip and splice in the premade masks, for use when credits/ED plays over episode content'''
    mask = core.std.BlankClip(clip)
    for i, mapping in enumerate(mask_mappings):
        maskclip = image_to_clip(clip, f'Masks/{episode}/{i+1}.png')
        mask = fvf.rfs(mask, maskclip, mapping)
    return mask


def mergecredits(clip: vs.VideoNode):
    '''Use an expression to merge the difference between NC's and source into the filtered video to protect credits'''
    merged1 = core.std.Expr(
        [src[op_start:op_end+1], ncop, clip[op_start:op_end+1]], ['x y - z +', ''])
    merged2 = core.std.Expr(
        [src[ed_start:ed_end+1], nced, clip[ed_start:ed_end+1]], ['x y - z +', ''])
    merged = clip[:op_start] + merged1 + \
        clip[op_end+1:ed_start] + merged2 + clip[ed_end+1:]
    return merged


def nc_replace(clip: vs.VideoNode):
    '''replace OP/ED with nc's to allow for merging later on to protect credits'''
    replaced = clip[:op_start] + ncop + \
        clip[op_end+1:ed_start] + nced + clip[ed_end+1:]
    return replaced


def edgefix(clip: vs.VideoNode, frame: int):
    '''Replace black bars and dodgy edges with redrawn edges'''
    go_crop, lucky_crop = 6, 12
    go_edges = image_to_clip(clip, "go fix.png")
    lucky_edges = image_to_clip(clip, "lucky fix.png")
    fix_go = vs.core.std.StackHorizontal([core.std.Crop(go_edges, right=1920-go_crop), core.std.Crop(
        clip, left=go_crop, right=go_crop), core.std.Crop(go_edges, left=1920-go_crop)])
    fix_lucky = vs.core.std.StackHorizontal([core.std.Crop(lucky_edges, right=1920-lucky_crop), core.std.Crop(
        clip, left=lucky_crop, right=lucky_crop), core.std.Crop(lucky_edges, left=1920-lucky_crop)])
    replaced = clip[:frame] + fix_go[frame:frame+6] + \
        fix_lucky[frame+6:frame+14] + clip[frame+14:]
    return replaced


def edgemask(clip: vs.VideoNode, retinex: bool = True):
    '''Create edgemask, either using kgf retinex edgemask or prewitt with minor adjustments'''
    if retinex:
        edge_mask = kgf.retinex_edgemask(src=clip)
    else:
        edge_mask = core.std.Prewitt(get_y(clip), planes=0)
        edge_mask = adjust.Tweak(edge_mask, cont=49)
        edge_mask = core.std.BoxBlur(edge_mask, vpasses=1, hpasses=1)
    return edge_mask


def antialias(clip: vs.VideoNode, mode: int = 1):
    '''AA clip using nnedi3 or eedi3 clamped'''
    if mode == 1:
        aa = lvf.aa.taa(clip, lvf.aa.nnedi3())
    else:
        aa = lvf.aa.nneedi3_clamp(clip)
    return aa


def rescale(clip: vs.VideoNode, aa: bool = True):
    '''Descale clip to native resolution and rescale toi output resolution using nnedi3.
    Masked for both credits and for lineart only. Performs AA on the clip as well if specified.'''
    descale = fvf.Debicubic(get_y(clip), width=native_width,
                            height=native_height, b=b, c=c)
    upscale = vdf.scale.nnedi3_upscale(descale)
    downscale = depth(muvf.SSIM_downsample(
        upscale, w=output_width, h=output_height, sigmoid=True), 16)
    rescaled = muvf.MergeChroma(downscale, clip)
    rescaled = fvf.rfs(rescaled, clip, exclude_rescale)
    if aa:
        rescaled = antialias(clip=rescaled, mode=1)
    lineart = core.std.MaskedMerge(
        clip, rescaled, mask=edgemask(clip=rescaled, retinex=False))
    masked_rescale = core.std.MaskedMerge(
        lineart, clip, mask=creditmask(clip=clip))
    return masked_rescale


def dehalo(clip: vs.VideoNode):
    dehaloclip = lvf.dehalo.masked_dha(clip, rx=1.5, ry=1.5)
    mappings = f'[{32755} {33298}]'
    replaced = fvf.rfs(clip, dehaloclip, mappings)
    return replaced


def denoise(clip: vs.VideoNode):
    '''Denoise luma based on brightness of the scene to avoid detail loss in dark areas, BM3D used for chroma'''
    max = 1 << clip.format.bits_per_sample
    lo, hi = round(max/20), round(max/20*19)
    luma_mask = vdf.mask.luma_mask(clip, thr_lo=lo, thr_hi=hi)
    denoised_chroma = att.BM3DCUDA(
        clip, sigma=[0, 1, 1], radius=2, filter_build='rtc')
    denoise_luma_strong = att.BM3DCUDA(
        clip, sigma=[1.5, 0, 0], radius=2, filter_build='rtc')
    denoise_luma_weak = att.BM3DCUDA(
        clip, sigma=[0.3, 0, 0], radius=2, filter_build='rtc')
    denoised_luma = core.std.MaskedMerge(
        denoise_luma_strong, denoise_luma_weak, luma_mask)
    denoised_merged = muvf.MergeChroma(denoised_luma, denoised_chroma)
    return denoised_merged


def deband(clip: vs.VideoNode):
    '''Masked deband and add grain using kgf luma mask as used with the denoising function'''
    debanded = gfa.GradFun3(clip, thr_det=1.6, detect_val=24,
                            grainy=0, grainc=0, smode=6, mask=2)
    grain = agm(debanded, strength=0.3,
                size=1.5, sharp=40, static=True, luma_scaling=9, grain_chroma=False)
    return grain


replaced = nc_replace(src)
rescaled = rescale(replaced, aa=1)
dehalod = dehalo(rescaled)
merged = mergecredits(dehalod)
fixed = edgefix(merged, frame=goframe)
denoised = denoise(fixed)
debanded = deband(denoised)
output = depth(debanded, 10)
output.set_output()
