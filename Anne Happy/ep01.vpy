# Anne Happy Episode 1

# imports
import vapoursynth as vs
import atomchtools as att
import gradfun_amod as gfa
import adjust
import lvsfunc as lvf
import kagefunc as kgf
import fvsfunc as fvf
import muvsfunc as muvf
import vardefunc as vdf
import mvsfunc as mvf
import havsfunc as hvf
from vsutil import *
from vsutil.clips import get_y

core = vs.core
core.max_cache_size = 11000
episode = '01'
end_frame = 34045
op_start, op_end = 6546, 8701
ed_start, ed_end, nced_offset = 32376, 33610, 920
native_width, native_height = 1280, 720  # as returned by getnative and anibin
output_width, output_height = 1920, 1080
kernel = 'bicubic'  # info only
b, c = 1/3, 1/3  # 0.2 0.5 possible but 1/3, 1/3 slighlty sharper & no issues identified
goframe = 32551  # black bars first frame


src = depth(lvf.src(r"Source/01.mkv", force_lsmas=True)[:end_frame+1], 16)
ncop = depth(lvf.src(r"Source/ncop.mkv", force_lsmas=True)
             [:op_end - op_start+1], 16)
nced = depth(lvf.src(r"Source/nced.mkv", force_lsmas=True)
             [nced_offset: nced_offset + ed_end-ed_start+1], 16)
mask_mappings = ['[31527 31598]', '[31611 31682]', '[31691 31759]', '[31791 31862]',
                 '[31875 31947]', '[32005 32092]', '[32105 32192]', '[32201 32268]', '[32278 32358]']


def image_to_clip(clip: vs.VideoNode, image: str):
    clipb = core.imwri.Read(image)
    clipb = core.std.AssumeFPS(clipb, fpsnum=clip.fps_num, fpsden=clip.fps_den)
    clipb = core.resize.Spline36(clipb, format=clip.format.id, matrix_s="709")
    clipb = core.std.Loop(clipb, end_frame-1)
    return clipb


def creditmask(clip: vs.VideoNode = src):
    mask = core.std.BlankClip(clip)
    for i, mapping in enumerate(mask_mappings):
        maskclip = image_to_clip(clip, f"Masks/{episode}/{i+1}.png")
        mask = fvf.rfs(mask, maskclip, mapping)
    return mask


def mergecredits(clip: vs.VideoNode):
    merged1 = core.std.Expr(
        [src[op_start:op_end+1], ncop, clip[op_start:op_end+1]], ['x y - z +', ''])
    merged2 = core.std.Expr(
        [src[ed_start:ed_end+1], nced, clip[ed_start:ed_end+1]], ['x y - z +', ''])
    merged = clip[:op_start] + merged1 + \
        clip[op_end+1:ed_start] + merged2 + clip[ed_end+1:]
    return merged


def nc_replace(clip: vs.VideoNode):
    replaced = clip[:op_start] + ncop + \
        clip[op_end+1:ed_start] + nced + clip[ed_end+1:]
    return replaced


def edgefix(clip: vs.VideoNode, frame: int):
    """Crop black bars and 2 scenes in the ED and resize back to output resolution"""
    mappings = f'[{frame} {frame + 5}] [{frame + 6} {frame + 13}]'
    cropped = core.std.Crop(clip, left=6, right=6, top=0, bottom=0)
    stretch = core.resize.Lanczos(cropped, output_width, output_height)
    replaced = fvf.ReplaceFramesSimple(clip, stretch, mappings=mappings)
    return replaced


def edgemask(clip: vs.VideoNode, retinex=True):
    """Create edgemask, either using kgf retinex edgemask or prewitt with minor adjustments"""
    if retinex:
        edge_mask = kgf.retinex_edgemask(src=clip)
    else:
        edge_mask = core.std.Prewitt(get_y(clip), planes=0)
        edge_mask = adjust.Tweak(edge_mask, cont=49)
        edge_mask = core.std.BoxBlur(edge_mask, vpasses=1, hpasses=1)
    return edge_mask


def antialias(clip: vs.VideoNode, strength: int = 1):
    """AA clip using nnedi3 or eedi3 clamped"""
    if strength == 1:
        aa = lvf.aa.taa(clip, lvf.aa.nnedi3())
    else:
        aa = lvf.aa.nneedi3_clamp(clip)
    return aa


def rescale(clip: vs.VideoNode, aa=True):
    """Descale clip to native resolution and rescale toi output resolution using nnedi3.
    Masked for both credits and for lineart only. Performs AA on the clip as well if specified."""
    descale = fvf.Debicubic(get_y(clip), width=native_width,
                            height=native_height, b=b, c=c)
    upscale = vdf.scale.nnedi3_upscale(descale)
    downscale = depth(muvf.SSIM_downsample(
        upscale, w=output_width, h=output_height, sigmoid=True), 16)
    rescaled = muvf.MergeChroma(downscale, clip)
    if aa > 0:
        rescaled = antialias(clip=rescaled, strength=aa)
    lineart = core.std.MaskedMerge(
        clip, rescaled, mask=edgemask(clip=rescaled, retinex=True))
    masked_rescale = core.std.MaskedMerge(
        lineart, clip, mask=creditmask(clip=clip))
    return masked_rescale


def denoise(clip: vs.VideoNode):
    """Denoise luma based on brightness of the scene to avoid detail loss in dark areas, BM3D used for chroma"""
    luma_mask = core.adg.Mask(clip.std.PlaneStats())
    #denoised_chroma = mvf.BM3D(clip, sigma=[0, 3, 3], radius1=1, CUDA=True)
    denoised_chroma = att.BM3DCUDA(
        clip, sigma=[0, 3, 3], radius=1, filter_build='rtc')
    denoise_luma_strong = hvf.SMDegrain(
        clip, thSAD=100, thSADC=0, tr=4, plane=4, chroma=True, prefilter=1, RefineMotion=True)
    denoise_luma_weak = hvf.SMDegrain(
        clip, thSAD=30, thSADC=0, tr=4, plane=4, chroma=True, prefilter=1, RefineMotion=True)
    denoised_luma = core.std.MaskedMerge(
        denoise_luma_strong, denoise_luma_weak, luma_mask)
    denoised_merged = muvf.MergeChroma(denoised_luma, denoised_chroma)
    return denoised_merged


def deband(clip: vs.VideoNode):
    """Quick masked deband and add grain using kgf luma mask as used with the denoising function"""
    deband = gfa.GradFun3(clip, thr_det=1.8, detect_val=28,
                          grainy=0, grainc=0, smode=6, mask=0)
    masked_deband = core.std.MaskedMerge(deband, clip, edgemask(clip=clip))
    grain = kgf.adaptive_grain(
        masked_deband, strength=0.25, static=True, show_mask=False)
    return grain


replaced = nc_replace(src)
rescaled = rescale(replaced, aa=1)
merged = mergecredits(rescaled)
fixed = edgefix(merged, frame=goframe)
denoised = denoise(fixed)
debanded = deband(denoised)
output = depth(debanded, 10)
output.set_output()
# src.set_output(1)
