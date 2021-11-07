# Anne Happy

![Anne Happy](Resources/Logo.png)

### Vapoursynth scripts and x264 settings

#### x264 10 bit 1080p encode for [Ambivalent-Subs](https://github.com/Ambivalent-subs), see comps here (links when complete)

###### _First vapoursynth script. Still lots I don't know so expect sub-optimal results :):_

---

* Splice in nc's to allow merging later on.

* Native res (720p) descale with debicubic 1/3 1/3.

* Reupscale with nnedi3/fsrcnnx and downscale back to 1080p with SSIM downsample.

* Apply nnedi3 AA to reduce any leftover ailising after rescaling.

* Dehalo part of the ED with maskedDHA, the whole scene looks awful and currently not too effective - help wanted - feel free to open an issue/pull request.

* Merge credits back in to filtered nc's and apply credit mask for credits that overlap with episode content (original masks courtesy of Baal).

* Replace edges of 2 scenes in the ED with messed up edges (original redraws also courtesy of Baal).

* Adaptive denoise using BM3D for luma and CCD for chroma with a stronger SMDegrain/KNLM clip used as reference for the luma denoising.

* Deband with gradfun3_amod then add static grain based on kgf luma mask via adptvgrnMod. Luma only and slighlty softer, larger grain for the aesthetic of the show.

* x264 settings - 10 bit, fairly generic and based on a few SCY/Beatrice x264 releases and a few guides. Aiming for decent compression but prioritses detail retention especially in darker frames.

_x264 build used - r3075 t_mod from [here](https://github.com/jpsdr/x264/releases)_

---

### Many Thanks to

* [Scyrous](https://github.com/Scyrous) - Setup help, lots of comments and pointers on VS and x264
* Baal - Sharing old SmugCat avs encode scripts and resources.
* [Light](https://github.com/LightArrowsEXE) - Setup help, pointers, general comments
* [Moe](https://github.com/Moelancholy) - Setup help, links and a lot of explaning.
* Various others in GJM #encoding for general help
* anti-raws for the JP BD-Remux.
