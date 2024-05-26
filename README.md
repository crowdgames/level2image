# level2image

To setup, run:

```
pip3 install pipenv
pipenv install
pipenv shell
```

On macOS you may need to install brew and run:

`brew install cairo`

Examples (to be run within pipenv):
```
# Text image
python3 level2image.py example/example.lvl

# Text image with no overlay
python3 level2image.py example/example.lvl --viz-none

# Text image with only path overlay
python3 level2image.py example/example.lvl --viz-none --viz path path line-arrow

# Text gif
python3 level2image.py example/example_frames/*.lvl --fmt=gif-anim

# Tileset image
python3 level2image.py example/example_with_spriteset.lvl --tile-image-folder=example/example_sprites

# Tileset gif
python3 level2image.py example/example_frames/*.lvl --fmt=gif-anim --tile-image-folder=example/example_sprites
```

Note for gifs: when using glob wildcards, frames are added in _alphabetical_ order (regardless of the order they appear in your file directory structure), so use prefix 0s in numbered frames.

eg:
```
without_prefixes
|   -- step0.lvl
|   -- step1.lvl
|   -- step10.lvl
|   -- step11.lvl
...
|   -- step2.lvl
|   -- step20.lvl

with_prefixes
|   -- step00.lvl
|   -- step01.lvl
|   -- step02.lvl
...
|   -- step10.lvl
|   -- step11.lvl
|   ...
|   -- step20.lvl
```
