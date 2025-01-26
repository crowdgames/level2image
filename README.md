# level2image

A utility for converting text level files to various image formats, with support for drawing overlays.

If you use this project in your work, please cite:

Cooper, S. (2024). level2image: A Utility for Making 2D Tile-Based Level Images with Overlays. Proceedings of the AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment, 20(1), 254-255. https://doi.org/10.1609/aiide.v20i1.31886


## Installation and setup

### Basic setup

You'll need Python 3.12 and pipenv installed.  To install pipenv, run:

```
pip3 install pipenv
```

To set up the pipenv environment, run:
```
pipenv install --categories svglib
```

Then you can launch a shell to run the utility with:
```
pipenv shell
```

There are some example usages below.


### Custom setup

The above instructions install the svglib converter, which seems to be more portable to different platforms.

If you'd like to use the cairosvg converter, you can instead run:

```
pipenv install --categories cairosvg
```

To use cairosvg, you may need to install the Cairo libraries specific to your platform. For example, on macOS you may need to install brew and run:

```
brew install cairo
```

Or on Linux:
```
apt install libcairo2
```

If you want both converters, you can run:
```
pipenv install --categories "cairosvg svglib"
```

If you only want to produce svgs, you don't need to install a converer, and can just run:

```
pipenv install
```


## Examples

These examples can be run in a `pipenv shell`:

```
# Text pdf
python level2image.py example/example.lvl

# Text svg
python level2image.py example/example.lvl --fmt svg

# Text pdf with no overlay
python level2image.py example/example.lvl --viz-none

# Text pdf with only path overlay
python level2image.py example/example.lvl --viz-none --viz path path line-arrow

# Tileset png
python level2image.py example/example_frames/step000.lvl --fmt=png --tile-image-folder=example/example_sprites --cell-size 64 --raster-scale 1

# Text gif
python level2image.py example/example_frames/*.lvl --fmt=gif-anim

# Tileset pdf
python level2image.py example/example_with_spriteset.lvl --tile-image-folder=example/example_sprites

# Tileset gif
python level2image.py example/example_frames/*.lvl --fmt=gif-anim --tile-image-folder=example/example_sprites --cell-size 32 --raster-scale 1

# Montage pdf - each png has up to 4x3 levels with 10 pixel spacing between columns and 20 between rows, with 5 padding around edges
python level2image.py example/example_frames/*.lvl --montage 4 3 10 20 --padding 5
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
