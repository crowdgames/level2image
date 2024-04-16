# level2image

To setup, run:

```
pip3 install pipenv
pipenv install
pipenv shell
```

On macOS you may need to install brew and run:

`brew install cairo`

For an example, within pipenv, run:

Basic image: `python3 level2image.py example.lvl`
Basic gif: `python3 level2image.py example_frames/*.lvl --fmt=gif-anim`

Note for gifs: frames are added in alphabetical order, so ensure that they are numbered with prefixed 0s - e.g, step10.lvl will be added before step2.lvl but not before step02.lvl.

Image with spriteset: `python3 level2image.py example_with_spriteset.lvl --tile-image-folder=example_sprites`
Gif with sprites: `python3 level2image.py example_frames/*.lvl --fmt=gif-anim --tile-image-folder=example_sprites`
