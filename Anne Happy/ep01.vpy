# Anne Happy Episode 1

# Imports
import vapoursynth as vs
import gradfun_amod as gfa
import havsfunc as hvf
import lvsfunc as lvf
import muvsfunc as muvf
import mvsfunc as mvf
import vardefunc as vdf

from atomchtools import BM3DCUDA as BM3DC
from ccd import ccd
from vsutil import depth
from vsutil import get_y as luma
from adptvgrnMod import adptvgrnMod as agm


core = vs.core
core.max_cache_size = 10000

# Info
episode = '01'
native_resolution = (1280, 720)
output_resolution = (1920, 1080)
kernel = 'bicubic'
b, c = 1/3, 1/3

# Zones for scene filtering/masking and frame replaces
zones = {
    "op": (6546, 8701),
    "ed": (32376, 33610),
    "dehalo": (32755,33298),
    "no rescale": (32545,32564),
    "go scene": (32551, 32557),
    "lucky scene": (32557, 32564),
    "masks": [(31527, 31598),(31611, 31682), (31691, 31759), (31791, 31862),(31875, 31947), (32005, 32092), (32105, 32192), (32201, 32268), (32278, 32358)]
        }

  

# Import sources + trim black frames and match nced/ncop to episode
src = core.lsmas.LWLibavSource(r"Source/01.mkv")[:-49]
ncop = core.lsmas.LWLibavSource(r"Source/ncop.mkv")[:-28]
nced = core.lsmas.LWLibavSource(r"Source/nced.mkv")[920:-29]


# Set filtering depth, (NB: BM3D ref and SSIM downsample 32 float)
src, ncop, nced = depth(src, 16), depth(ncop, 16), depth(nced, 16)

# Miscellaneous function just to make mask building a bit simpler

def imagetoclip(clip: vs.VideoNode, image: str) -> vs.VideoNode:
    '''Imports the image from the specified path, resizes to match the video format/fps then loops to cover the full video length for use with in frame replaces'''
    input = core.imwri.Read(image)
    format = core.resize.Spline36(input, format=clip.format.id, matrix_s="709")
    fps = core.std.AssumeFPS(format, clip)
    loop = core.std.Loop(fps, clip.num_frames-1)
    return loop

# Prepare/fix parts of source before filtering

def nc(clip: vs.VideoNode) -> vs.VideoNode:
    '''Replace OP/ED with nc's to allow for merging later instead of creating a credit mask'''
    ops, ope = zones["op"]
    eds, ede = zones["ed"]
    replaced = clip[:ops] + ncop + clip[ope+1:eds] + nced + clip[ede+1:]
    return replaced

def edgefix(clip: vs.VideoNode) -> vs.VideoNode:
    '''Replace black bars and scene bleeding on 2 scenes with redrawn edges'''
    crop = 6
    go = imagetoclip(clip, "Resources\Edgefix\go.png")
    left = core.std.Crop(go, right=go.width-crop)
    middle = core.std.Crop(clip, left=crop, right=crop)
    right = core.std.Crop(go, left=go.width-crop)
    gofixed = core.std.StackHorizontal([left, middle, right])
    replaced = lvf.rfs(clip, gofixed, zones["go scene"])

    crop = 12
    lucky = imagetoclip(clip, "Resources\Edgefix\lucky.png")
    left = core.std.Crop(lucky, right=lucky.width-crop)
    middle = core.std.Crop(clip, left=crop, right=crop)
    right = core.std.Crop(lucky, left=lucky.width-crop)
    luckyfixed = core.std.StackHorizontal([left, middle, right])
    replaced = lvf.rfs(replaced, luckyfixed, zones["lucky scene"])
    return replaced 

# Masks

def creditmask(clip: vs.VideoNode) -> vs.VideoNode:
    '''Create a blank clip and splice in the premade masks, for use when credits/ED plays over episode content'''
    mask = core.std.BlankClip(clip)
    for i, mapping in enumerate(zones["masks"]):
        maskclip = imagetoclip(clip, f'Resources/Masks/{episode}/{i+1}.png')
        mask = lvf.rfs(mask, maskclip, mapping)
    return mask

def edgemask(clip: vs.VideoNode) -> vs.VideoNode:
    '''
    Create edgemask to isolate lineart/textures for use in rescaling.
    Trying to exclude as most/all noise while detecting as many edges/details as possible.
    '''
    clip=luma(clip)
    # max is set depending on depth of the source
    max = 1 << clip.format.bits_per_sample
    # Strong denoise to help edge detection without picking up noise (to avoid rescaling noise)
    denoised = roughdenoise(clip=clip, mode=2)
    # Retinex to help improve contrast to pick out edges which may not be detetcted
    retinex = core.retinex.MSRCP(denoised, sigma=[50, 200, 350], upper_thr=0.005)
    inputs = [denoised, retinex]
    outputs= []
    # Process both the retinex and denoised clip (both pick out certain lines/edges better than the other)
    for input in inputs:
        # TCanny with prewitt
        edges = core.tcanny.TCanny(input, mode=1, sigma=0.4, op=1)
        # Reduce brightness a bit (as will be merged) and cutoff some faint details - mainly looking for just lineart/main edges
        lineart = core.std.Levels(edges, max_out=max*0.6, gamma=0.9)
        # brighten clip to bring out feint details then darken entire clip so this can be merged with the core edges in the lineart clip
        textures = core.std.Levels(edges, gamma=1.5).std.Levels(max_out=max*0.3)
        # merge textures and lineart and store in the output list so the denoised/retinex results can be merged
        outputs.append(core.std.Expr([lineart, textures], ['x y +']))
    # merge both the denoised and retinex edgemasks for more overall coverage (also helps to somewhat brigthen up the edges)    
    mask = core.std.Expr([outputs[0], outputs[1]], ['x y +'])
    return mask

def lumamask(clip: vs.VideoNode) -> vs.VideoNode:
    '''simple luma mask from vardefunc to identify dark areas for adaptive processing'''
    # max is set depending on depth of the source    
    max = 1 << clip.format.bits_per_sample
    # set top end to be mostly fully black giving just the mid -> darker areas being between black and white
    low, high = round(0), round(max*(0.5))
    mask = vdf.mask.luma_mask(clip, thr_lo=low, thr_hi=high)
    return mask


# Main functions

# Simple AA called in the rescaleAA function, just to try and pick up any residual alisaing

def antialias(clip: vs.VideoNode) -> vs.VideoNode:
    '''AA clip using nnedi3 to try and fix and residual AA left after rescaling'''
    aa = lvf.aa.taa(clip, lvf.aa.nnedi3(opencl=True))
    return aa

# kernel for downscaling could be bicubic 0.2 0.5, went with 1/3 1/3 as sharper and not seemingly causing issues

def rescaleAA(clip: vs.VideoNode) -> vs.VideoNode:
    '''
    Descale luma to native resolution and rescale to output resolution using nnedi3 and fsrcnnx.
    Masked for lineart only and to exclude credits not covered by the credit merge.
    Also applies additional AA after downscaling to try and remove any left over aliasing. 
    '''
    dw, dh = native_resolution
    ow, oh = output_resolution
    # Path to shader file FSRCNNX_x2_56-16-4-1.gsgl used
    shader = r"Resources/FSRCNNX.glsl"
    # Descale luma to native resolution using closest match when determing the original kernel used.
    descale = core.descale.Debicubic(luma(clip), width=dw, height=dh, b=b, c=c)
    # Upscale 2x with nnedi3 - used as the soft clip reference to weight against fsrcnnx
    nn3 = vdf.scale.nnedi3cl_double(clip=descale, use_znedi=True) 
    # Upscale with fsrcnnx referencing the nnedi3 clip - weighted strongly towards the nnedi3 clip as I think it helps to prevent fsrc overshooting.
    upscale = vdf.scale.fsrcnnx_upscale(clip=descale, width=2*dw, height=2*dh, shader_file=shader, upscaled_smooth=nn3, strength=30, profile='slow')
    # Downscale with SSMI downsample, NB outputs 32bit clip
    downscale = muvf.SSIM_downsample(upscale, w=ow, h=oh, sigmoid=True)
    # Merge chroma back from source to the rescaled luma, NB: SSIM outputs 32 bit float
    rescaled = muvf.MergeChroma(depth(downscale,16), clip)
    # Scenes with text in the ED not picked up by a diffmask but seems to creat issues - exlcuded them from rescaling
    excluded = lvf.rfs(rescaled, clip, zones["no rescale"])
    # AA clip to try and remove any left over aliasing see the antialias function
    aa = antialias(clip=excluded)
    # Mask to scale just lineart/edges to avoid rescale/sharpening a bunch of noise
    lineart = core.std.MaskedMerge(clip, aa, edgemask(clip=clip))
    # Additional mask to protect credits over episode content - not covered by the mergecredits function
    masked = core.std.MaskedMerge(lineart, clip, creditmask(clip=clip))
    return masked

def dehalo(clip: vs.VideoNode):
    '''Dehalo using maskedDHA for a scene in the ED'''
    dehaloclip = lvf.dehalo.masked_dha(clip, rx=1.5, ry=1.5)
    replaced = lvf.rfs(clip, dehaloclip, zones["dehalo"])
    return replaced

def denoise(clip: vs.VideoNode) -> vs.VideoNode:
    '''
    Adaptive luma denoising using BM3D with reference clip from SMDegrain/KNLM.
    CCD used for chroma (mainly to remove some blotchy chroma noise on a few scenes)
    Contrasharpened, using the original and final merged denoised clip.
    '''
    # Use KNLM/SMD pass to clear a significant amount of noise for use as a reference clip
    ref = roughdenoise(clip=clip, mode=1)
    BM3DC_args = dict(block_step=4, bm_range=16, radius=2, ps_num=2, ps_range=6, fast=False, filter_build='rtc')
    BM3D_args = dict(radius1=2, profile1='np')
    # Strong luma denoise, trying to shift some dynamic noise while minimising the risk of detail loss
    strong = BM3DC(source=luma(clip), ref=depth(luma(ref),32), sigma=2, **BM3DC_args) 
    # Weaker denoise to help prevent detail loss in dark areas
    weak = mvf.BM3D(input=luma(clip), ref=luma(ref), sigma=0.5, **BM3D_args)
    # Chroma with CCD (mainly picked as a nice balance for speed/quality compared to BM3D for chroma)
    chroma = ccd(clip=clip, threshold=4.5, matrix="709")
    # Apply denosing based on luma mask -> heavily tweaked so mid->lighter areas are fully denoised
    denoised = core.std.MaskedMerge(strong, weak, lumamask(clip))
    # Merge luma and chroma back
    merged = muvf.MergeChroma(denoised, chroma)
    # Contrasharpen to try and prevent softening of lines in the denoised clip
    contra = hvf.ContraSharpening(denoised=merged, original=clip, radius=3, rep=24, planes=0)
    return contra

def roughdenoise(clip: vs.VideoNode, mode: int):
    '''
    Brute force luma denoise for usage with masks and for ref clips.
    Mode 1: Reference denoise
    Mode 2: Strong KNLM/SMDegrain pass to shift the majority of noise
    '''
    KNLM_args = dict(d=3, a=4, channels='Y')
    if mode == 1:
        # Reference denoise, KNLM seems to clear lots of noise but smears a bit, so low value used
        SMD_args = dict(tr=4, pel=2, subpixel=3, plane=0, prefilter=1, search=6, RefineMotion=True)
        denoised = core.knlm.KNLMeansCL(clip=clip, h=0.15, **KNLM_args)
        denoised = hvf.SMDegrain(input=denoised, thSAD=85, **SMD_args)
        denoised = hvf.ContraSharpening(denoised=denoised, original=clip, rep=24, planes=0)
    else:
        # Brute force denoise - aiming to elimate all noise for use in masks
        SMD_args = dict(tr=3, plane=0, prefilter=1, RefineMotion=True)
        denoised = core.knlm.KNLMeansCL(clip=clip, h=1.2, **KNLM_args)
        denoised = hvf.SMDegrain(input=denoised, thSAD=150, **SMD_args)
        denoised = hvf.ContraSharpening(denoised=denoised, original=clip, rep=24, planes=0)
    return denoised

def deband(clip: vs.VideoNode) -> vs.VideoNode:
    '''Conservative deband with gradfun3 and apply grain adaptively using adg luma mask'''
    debanded = gfa.GradFun3(clip, thr_det=2, detect_val=32, grainy=0, grainc=0, smode=6, mask=2)
    # Softer/slight larger grain to suit the shows softer aesthetic, applied based on adg luma mask from kagefunc
    grain = agm(debanded, strength=0.35, size=1.35, sharp=40, static=True, luma_scaling=9, grain_chroma=False)
    return grain

def mergecredits(clip: vs.VideoNode, src: vs.VideoNode = src) -> vs.VideoNode:
    '''Use an expression to merge the difference between NC's and source into the filtered video to protect credits'''
    ops, ope = zones["op"]
    eds, ede = zones["ed"]
    # Adds the difference between the src (op/ed) and original nc's to the filtered nc's which adds the credits back in (alternative method to masking the credits)
    merged_op = core.std.Expr([src[ops:ope+1], ncop, clip[ops:ope+1]], ['x y - z +', ''])
    merged_ed = core.std.Expr([src[eds:ede+1], nced, clip[eds:ede+1]], ['x y - z +', ''])
    merged = clip[:ops] + merged_op + clip[ope+1:eds] + merged_ed + clip[ede+1:]
    # Causing dirty lines over the edgefix for some reason? maybe slight difference between nced and episode version, replace (no credits here anyway)
    excluded = lvf.rfs(merged, clip, [zones["go scene"], zones["lucky scene"]])
    return excluded


#Filter chain
replaced = nc(src)
fixed = edgefix(replaced)
rescaled = rescaleAA(fixed)
dehalod = dehalo(rescaled)
merged = mergecredits(dehalod)
denoised = denoise(merged)
debanded = deband(denoised)
output = depth(debanded, 10)
output.set_output()
