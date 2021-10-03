# Anne Happy

### Vapoursynth script and encoding settings.

#### x264 10 bit 1080p encode for [Ambivalent-Subs](https://github.com/Ambivalent-subs), see comps here (link when complete)

###### _First vs script. Not really sure what I'm doing_

---

* Splice in nc's to allow merging later on.

* Native res (720p) descale with debicubic 1/3 1/3

* Reupscale with nnedi3 and downscale back to 1080p with SSIM downsample

* Apply nnedi3 AA.

* Dehalo part of the ED with maskedDHA.

* Merge credits back in to filtered nc's/apply credit mask for over episode credits (original manual masks courtesy of Baal).

* Replace edges of 2 scenes in the ED with messed up edges (original redraws also courtesy of Baal).

* Denoise with BM3D, applying luma denoising based on kgf luma mask to protect darker areas.

* Small deband with gradfun3 then add some grain based on kgf luma mask.

* x264 settings - 10 bit, fairly generic. Aiming for decent compression but prioritses detail retention.

---

### Many Thanks to:

- [Scyrous](https://github.com/Scyrous) - Setup help, lots of comments and pointers on VS and x264
- Baal - sharing old SmugCat avs encode scripts and resources.
- [Light](https://github.com/LightArrowsEXE) - Setup help, pointers, general comments
- [Moe](https://github.com/Moelancholy) - Setup help, links, lot's of explaining.
- Zewia, Julek and various others in GJM #encoding
