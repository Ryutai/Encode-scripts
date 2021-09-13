#Anne Happy Episode 1
# # imports
import vapoursynth as vs
import gradfun_amod as gfa
import adjust
import lvsfunc as lvf
import kagefunc as kgf
import fvsfunc_mod as fvf
import muvsfunc as muvf
import vardefunc as vdf
import mvsfunc as mvf
import havsfunc as hvf
from vsutil import *
from vsutil.clips import get_y

core = vs.core

src = depth(lvf.src(r"Source/EP01.mkv")[:34044],16) #34044 # source - trim black frames
native_width, native_height = 1280, 720
output_width, output_height = 1920, 1080
kernel = 'bicubic' # info only
b, c = 1/3, 1/3  # 0.2 0.5 possible but 1/3, 1/3 slighlty sharper & no issues
opstart, opend = 6544, 8701 
edstart, edend = 31521, 33608
goframe = 32550 #black bars first frame

def edgefix(clip: vs.VideoNode, go_frame: int):
    mappings = f"[{go_frame} {go_frame + 5}] [{go_frame + 6} {go_frame + 13}]"
    cropped = core.std.Crop(clip, left=6, right=6, top=0, bottom=0)
    stretch = core.resize.Lanczos(cropped, output_width, output_height)
    replaced = fvf.ReplaceFramesSimple(clip, stretch, mappings=mappings)
    return replaced

def creditmask(clip: vs.VideoNode,descale: vs.VideoNode):
    rescaled = core.resize.Bicubic(get_y(descale), output_width, output_height, filter_param_a=b, filter_param_b=c)
    diffmask = core.std.Expr([get_y(clip), get_y(rescaled)], 'x y - abs')
    expand, inflate = 10, 7
    for _ in range(expand):
        diffmask = core.std.Maximum(diffmask, planes=0)
    for _ in range(inflate):
        diffmask = core.std.Inflate(diffmask, planes=0)
    credit_mask = adjust.Tweak(diffmask, cont=100)
    credit_mask = core.std.BoxBlur(credit_mask,vpasses=30, hpasses=30)
    return credit_mask    

def edgemask(clip: vs.VideoNode, retinex=True):
    if retinex:
        edge_mask = kgf.retinex_edgemask(src=clip)
    else:
        edge_mask = core.std.Prewitt(get_y(clip), planes=0)
        edge_mask = adjust.Tweak(edge_mask, cont=35)
        edge_mask = core.std.BoxBlur(edge_mask, vpasses=2, hpasses=2)
    return edge_mask

def antialias(clip: vs.VideoNode, strength: int=1):
    if strength == 1:
        aa = lvf.aa.taa(clip,lvf.aa.nnedi3())
    else:
        aa =lvf.aa.nneedi3_clamp(clip)
    return aa


def rescale(clip: vs.VideoNode, aa=True):
    descale = fvf.Debicubic(get_y(clip), width=native_width, height=native_height, b=b, c=c)
    upscale = vdf.scale.nnedi3_upscale(descale)
    downscale = depth(muvf.SSIM_downsample(upscale, w=output_width, h=output_height, sigmoid=True),16) 
    rescaled = (muvf.MergeChroma(downscale, src))
    if aa > 0:
       rescaled = antialias(clip=rescaled, strength=aa)
    credit_mask, edge_mask = creditmask(clip=clip,descale=descale),edgemask(clip=rescaled, retinex=True)
    lineart = core.std.MaskedMerge(clip, rescaled, mask=edge_mask)
    masked_rescale = core.std.MaskedMerge(lineart, clip, mask=credit_mask)
    return masked_rescale

def denoise(clip=src):
    luma_mask = core.adg.Mask(clip.std.PlaneStats())
    denoised_chroma = mvf.BM3D(clip, sigma=[0, 4, 4], radius1=1)
    denoise_luma_strong = hvf.SMDegrain(clip, thSAD=150, thSADC=0, tr=4, plane=4, chroma=True, prefilter=1, RefineMotion=True)
    denoise_luma_weak = hvf.SMDegrain(clip, thSAD=80, thSADC=0, tr=4, plane=4, chroma=True, prefilter=1, RefineMotion=True)
    denoised_luma = core.std.MaskedMerge(denoise_luma_strong, denoise_luma_weak, luma_mask)
    denoised_merged = muvf.MergeChroma(denoised_luma, denoised_chroma)
    return denoised_merged

def deband_grain(clip=src):
    deband = gfa.GradFun3(clip, thr_det=1.5, detect_val=32, grainy=0, grainc=0, smode=6, mask=0)
    masked_deband = core.std.MaskedMerge(deband, clip, edgemask(clip=clip))
    grain = kgf.adaptive_grain(masked_deband, strength=0.25, static=True, show_mask=False)
    return grain



rescaled = rescale(src, aa=1)
fixed = edgefix(rescaled, go_frame)
denoised = denoise(fixed)
deband = deband_grain(denoised)
output = depth(deband,10)
output.set_output()


