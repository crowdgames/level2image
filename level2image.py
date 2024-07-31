import argparse, base64, io, json, math, os, pathlib, sys
import PIL.Image

RECT_NONE         = 'none'
RECT_FILL         = 'fill'
RECT_FILL_UNIQ    = 'fill-uniq'
RECT_OUTLINE      = 'outline'
RECT_BORDER       = 'border'
RECT_LIST         = [RECT_NONE, RECT_FILL, RECT_FILL_UNIQ, RECT_OUTLINE, RECT_BORDER]

PATH_NONE         = 'none'
PATH_LINE         = 'line'
PATH_ARC          = 'arc'
PATH_LINE_POINT   = 'line-point'
PATH_ARC_POINT    = 'arc-point'
PATH_LINE_ARROW   = 'line-arrow'
PATH_ARC_ARROW    = 'arc-arrow'
PATH_LINE_DASH    = 'line-dash'
PATH_ARC_DASH     = 'arc-dash'
PATH_LINE_THICK   = 'line-thick'
PATH_ARC_THICK    = 'arc-thick'
PATH_LIST         = [PATH_NONE, PATH_LINE, PATH_ARC, PATH_LINE_POINT, PATH_ARC_POINT, PATH_LINE_ARROW, PATH_ARC_ARROW, PATH_LINE_DASH, PATH_ARC_DASH, PATH_LINE_THICK, PATH_ARC_THICK]

SHAPE_PATH        = 'path'
SHAPE_LINE        = 'line'
SHAPE_TILE        = 'tile'
SHAPE_RECT        = 'rect'
SHAPE_LIST        = [SHAPE_PATH, SHAPE_LINE, SHAPE_TILE, SHAPE_RECT]

FMT_SVG           = 'svg'
FMT_PDF           = 'pdf'
FMT_PNG           = 'png'
FMT_GIF_ANIM      = 'gif-anim'
FMT_LIST          = [FMT_SVG, FMT_PDF, FMT_PNG, FMT_GIF_ANIM]

class GroupShapeStyleAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super().__init__(option_strings, dest, nargs, **kwargs)
        if nargs != '+':
            raise ValueError('nargs can only be +')

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 3:
            parser.error('argument %s: expected at most three arguments' % option_string)

        while len(values) < 3:
            values.append(None)

        values_list = getattr(namespace, self.dest, None)

        if values_list is None:
            values_list = []
            setattr(namespace, self.dest, values_list)

        values_list.append(values)

class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_args(self, action, default_metavar):
        if isinstance(action, GroupShapeStyleAction):
            return 'GROUP [SHAPE [STYLE]]'
        else:
            return super()._format_args(action, default_metavar)

parser = argparse.ArgumentParser(description='Create image from level file.', formatter_class=CustomHelpFormatter)
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument('--background-files', type=str, nargs='+', help='Input background images.')
group.add_argument('--background-suffix', type=str, help='Suffix to remove from filenames when looking for backgrounds.')
group.add_argument('--background-none', action='store_true', help='Don\'t automatically use background images if present.')

parser.add_argument('--size-font', type=int, help='Font size.', default=8)
parser.add_argument('--size-cell', type=int, help='cell size.', default=11)
parser.add_argument('--cfgfile', type=str, help='Config file.')
parser.add_argument('--suffix', type=str, help='Extra suffix to add to output file.', default='.out')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--viz', type=str, nargs='+', action=GroupShapeStyleAction, help='How to display the group GROUP; SHAPE from: ' + ','.join(SHAPE_LIST) + '; STYLE from: ' + ','.join(PATH_LIST) + ' or ' + ','.join(RECT_LIST) + '.')
parser.add_argument('--viz-hide', type=str, metavar='GROUP', action='append', help='Hide a group.')
parser.add_argument('--viz-none', action='store_true', help='Hide all groups other than those displayed.')
parser.add_argument('--viz-color', type=str, nargs=2, metavar=('GROUP', 'COLOR'), action='append', help='Which color to display a group.')
parser.add_argument('--no-avoid', action='store_true', help='Don\'t try to avoid previous edges on path.')
parser.add_argument('--no-blank', action='store_true', help='Don\'t output blank tiles.')
parser.add_argument('--tile-image-folder', type=str, help='Folder to look for tile images in.')
parser.add_argument('--padding', type=int, help='Padding around edges.', default=0)
parser.add_argument('--anim-delay', type=int, help='Frame delay for animation (in ms).', default=250)
parser.add_argument('--raster-scale', type=int, help='Amount to scale raster images by.', default=2)

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument('--cairosvg', action='store_true', help='Only try to use cairosvg converter.')
group.add_argument('--svglib', action='store_true', help='Only try to use svglib converter.')

args = parser.parse_args()

if args.stdout and args.fmt != FMT_SVG:
    raise RuntimeError('can only write svg to stdout')

if args.cfgfile is None:
    args.cfgfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfg-default.json')

with open(args.cfgfile, 'rt') as cfgfile:
    cfg = json.load(cfgfile)

if args.background_files is not None and len(args.background_files) != len(args.levelfiles):
    raise RuntimeError('must have same number of levels and backgrounds')



def distance(ra, ca, rb, cb):
    return ((ra - rb)**2 + (ca - cb)**2)**0.5

def is_between(ra, ca, rb, cb, rc, cc):
    if (ra, ca) == (rb, cb) or (rc, cc) == (rb, cb):
        return False
    return abs(distance(ra, ca, rb, cb) + distance(rb, cb, rc, cc) - distance(ra, ca, rc, cc)) < 0.01

def svg_rect(r0, c0, rsz, csz, padding, sides, style, color, drawn):
    if (rsz, csz) == (0, 0):
        print(' - WARNING: skipping zero-size rect: %f %f %f %f' % (r0, c0, rsz, csz))
        return ''

    if style == RECT_FILL_UNIQ and (r0, c0, rsz, csz) in drawn:
        return ''

    drawn.add((r0, c0, rsz, csz))

    if style in [RECT_FILL, RECT_FILL_UNIQ]:
        style_svg = 'stroke:none;fill:%s;fill-opacity:0.3' % (color)
        inset = 0
    elif style in [RECT_OUTLINE]:
        style_svg = 'stroke:%s;fill:none' % (color)
        inset = 0.5
    elif style in [RECT_BORDER]:
        style_svg = 'stroke:%s;stroke-width:1.5;fill:none' % (color)
        inset = 0
    else:
        raise RuntimeError('unknown style: %s' % style)

    x0 = c0 * args.size_cell + inset + padding
    xsz = csz * args.size_cell - 2 * inset
    if xsz <= 0:
        x0 = (c0 + 0.5 * (csz - 0.01)) * args.size_cell + padding
        xsz = 0.01

    y0 = r0 * args.size_cell + inset + padding
    ysz = rsz * args.size_cell - 2 * inset
    if ysz <= 0:
        y0 = (r0 + 0.5 * (rsz - 0.01)) * args.size_cell + padding
        ysz = 0.01

    if style == RECT_BORDER:
        top, bottom, left, right = sides
        ret = ''
        if top:
            ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" style="%s" stroke-linecap="square"/>\n' % (x0, y0, x0 + xsz, y0, style_svg)
        if bottom:
            ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" style="%s" stroke-linecap="square"/>\n' % (x0, y0 + ysz, x0 + xsz, y0 + ysz, style_svg)
        if left:
            ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" style="%s" stroke-linecap="square"/>\n' % (x0, y0, x0, y0 + ysz, style_svg)
        if right:
            ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" style="%s" stroke-linecap="square"/>\n' % (x0 + xsz, y0, x0 + xsz, y0 + ysz, style_svg)
        return ret
    else:
        if sides is not None:
            raise RuntimeError('can\'t use sides with style: %s' % style)
        return '  <rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" style="%s"/>\n' % (x0, y0, xsz, ysz, style_svg)

def svg_line(r1, c1, r2, c2, padding, color, require_arc, arc_avoid_edges, from_circle, to_circle, to_arrow, to_point, dash, thick):
    x1 = (c1 + 0.5) * args.size_cell + padding
    y1 = (r1 + 0.5) * args.size_cell + padding
    x2 = (c2 + 0.5) * args.size_cell + padding
    y2 = (r2 + 0.5) * args.size_cell + padding

    opts_shape = ''
    if thick:
        opts_shape += (' stroke="%s"' % color)
        opts_shape += ' stroke-width="2"'
    else:
        opts_shape += ' stroke="none"'

    opts_line = ''
    if dash:
        opts_line += ' stroke-dasharray="3"'

    if thick:
        opts_line += ' stroke-width="2"'
    else:
        opts_line += ' stroke-width="1"'

    ret = ''
    if from_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" fill="%s"%s/>\n' % (x1, y1, color, opts_shape)
    if to_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" fill="%s"%s/>\n' % (x2, y2, color, opts_shape)

    if (r1, c1) == (r2, c2):
        print(' - WARNING: skipping zero-length edge: %f %f %f %f' % (r1, c1, r2, c2))
        return ret

    if x1 < x2:
        orthx = (y2 - y1) / 4
        orthy = (x1 - x2) / 4
    else:
        orthx = (y1 - y2) / 4
        orthy = (x2 - x1) / 4
    orthmax = 0.75 * args.size_cell
    orthlen = distance(0, 0, orthx, orthy)

    orthx = orthx / orthlen * orthmax
    orthy = orthy / orthlen * orthmax

    midx = (x1 + x2) / 2
    midy = (y1 + y2) / 2
    curvex = midx + orthx
    curvey = midy + orthy

    as_arc = require_arc
    if not as_arc and arc_avoid_edges is not None:
        for (rj1, cj1, rj2, cj2) in arc_avoid_edges:
            if is_between(r1, c1, rj1, cj1, r2, c2):
                as_arc = True
                break
            if is_between(r1, c1, rj2, cj2, r2, c2):
                as_arc = True
                break
            if (r1, c1, r2, c2) == (rj2, cj2, rj1, cj1):
                if (r1, c1, r2, c2) < (rj1, cj1, rj2, cj2):
                    as_arc = True
                    break

    if to_point:
        ret += '  <circle cx="%.2f" cy="%.2f" r="1" fill="%s"%s/>\n' % (x2, y2, color, opts_shape)

    if to_arrow:
        if as_arc:
            adjust = distance(x1, y1, x2, y2)
            adjust = max(0.0, min(1.0, (adjust - 10) / (50 - 10))) * 0.4 + 0.6
            rotate = math.degrees(math.atan2(y2 - (midy + adjust * orthy), x2 - (midx + adjust * orthx)))
        else:
            rotate = math.degrees(math.atan2(y2 - y1, x2 - x1))

        ret += '  <g transform="translate(%.2f %.2f) rotate(%.2f)"><polygon points="0 0, -4 -2, -4 2" fill="%s"%s/></g>\n' % (x2, y2, rotate, color, opts_shape)

    if as_arc:
        ret += '  <path d="M %.2f %.2f Q %.2f %.2f %.2f %.2f" stroke="%s" stroke-linecap="round" fill="none"%s/>\n' % (x1, y1, curvex, curvey, x2, y2, color, opts_line)
    else:
        ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-linecap="round"%s/>\n' % (x1, y1, x2, y2, color, opts_line)

    return ret

def load_image(filename):
    file_image = PIL.Image.open(filename).convert('RGBA')
    fresh_image = PIL.Image.new(file_image.mode, file_image.size)
    fresh_image.putdata(file_image.getdata())
    return fresh_image

def b64_image(image):
    byte_data = io.BytesIO()
    image.save(byte_data, 'png')
    byte_data.flush()
    byte_data.seek(0)
    b64_data = base64.b64encode(byte_data.read()).decode('ascii')
    return b64_data

def load_b64_image(filename):
    return b64_image(load_image(filename))



def initialize_cairosvg():
    try:
        import cairosvg

        def _svg2pdf(svg):
            return cairosvg.svg2pdf(svg)

        def _svg2png(svg, svg_width, svg_height, svg_scale):
            return cairosvg.svg2png(svg, background_color='#ffffff', parent_width=svg_width, parent_height=svg_height, output_width=svg_width*svg_scale, output_height=svg_height*svg_scale)

        return _svg2pdf, _svg2png

    except ImportError:
        return None

def initialize_svglib():
    try:
        import svglib.svglib
        import reportlab.graphics.renderPDF
        import reportlab.graphics.renderPM

        def _adjustNode(node, raster_scale):
            if raster_scale is not None:
                if hasattr(node, 'strokeWidth'):
                    node.strokeWidth *= raster_scale
                if hasattr(node, 'fontName'):
                    node.fontName = 'Courier-Bold'

            if hasattr(node, 'text'):
                node.fontSize += 0.5
                node.y -= (node.fontSize * 0.25)

            if hasattr(node, 'getContents'):
                for child in node.getContents():
                    _adjustNode(child, raster_scale)

        def _svg2rlg(svg, raster_scale):
            drawing = svglib.svglib.svg2rlg(io.StringIO(svg))
            for content in drawing.contents:
                _adjustNode(content, raster_scale)
            return drawing

        def _svg2pdf(svg):
            return reportlab.graphics.renderPDF.drawToString(_svg2rlg(svg, None))

        def _svg2png(svg, svg_width, svg_height, svg_scale):
            return reportlab.graphics.renderPM.drawToString(_svg2rlg(svg, svg_scale), fmt='PNG', dpi=72 * svg_scale, backend='_renderPM')

        return _svg2pdf, _svg2png

    except ImportError:
        return None

def initialize_unsupported():
    def _svg2pdf(svg):
        print('Unsupported conversion to pdf. Try installing packages for cairosvg or svglib.')
        sys.exit(-1)

    def _svg2png(svg, svg_width, svg_height, svg_scale):
        print('Unsupported conversion to image. Try installing packages for cairosvg or svglib.')
        sys.exit(-1)

    return _svg2pdf, _svg2png


svg2pdf, svg2png = None, None

initializers = [(initialize_cairosvg, 'cairosvg', not args.svglib),
                (initialize_svglib, 'svglib', not args.cairosvg),
                (initialize_unsupported, 'unsupported', not (args.svglib or args.cairosvg))]

for initializer, name, attempt in initializers:
    if attempt:
        result = initializer()
        if result is not None:
            svg2pdf, svg2png = result
            print('using converter', name)
            break

if svg2pdf is None or svg2png is None:
    print('no converter found')
    sys.exit(-1)


DRAW_STYLE_DEFAULT = {}
DRAW_STYLE_DEFAULT[SHAPE_PATH] = PATH_LINE_ARROW
DRAW_STYLE_DEFAULT[SHAPE_LINE] = PATH_LINE_ARROW
DRAW_STYLE_DEFAULT[SHAPE_RECT] = RECT_OUTLINE
DRAW_STYLE_DEFAULT[SHAPE_TILE] = RECT_FILL

draw_style = {}
draw_style[None] = dict(DRAW_STYLE_DEFAULT)

if args.viz_none:
    draw_style = {}
    draw_style[None] = {}
    draw_style[None][SHAPE_PATH] = PATH_NONE
    draw_style[None][SHAPE_LINE] = PATH_NONE
    draw_style[None][SHAPE_RECT] = RECT_NONE
    draw_style[None][SHAPE_TILE] = RECT_NONE

if args.viz_hide is not None:
    for group in args.viz_hide:
        draw_style[group] = {}
        draw_style[group][SHAPE_PATH] = PATH_NONE
        draw_style[group][SHAPE_LINE] = PATH_NONE
        draw_style[group][SHAPE_RECT] = RECT_NONE
        draw_style[group][SHAPE_TILE] = RECT_NONE

if args.viz is not None:
    for group, shape, style in args.viz:
        if group not in draw_style:
            draw_style[group] = {}

        if shape is None:
            shape_to_style = DRAW_STYLE_DEFAULT
        elif shape in SHAPE_LIST:
            if style is None:
                style = DRAW_STYLE_DEFAULT[shape]
            shape_to_style = {shape:style}
        else:
            raise RuntimeError('unknown shape: %s' % shape)

        for shape, style in shape_to_style.items():
            if (shape in [SHAPE_PATH, SHAPE_LINE] and style not in PATH_LIST) or (shape in [SHAPE_RECT, SHAPE_TILE] and style not in RECT_LIST):
                raise RuntimeError('shape and style mismatch: %s %s' % (shape, style))

            draw_style[group][shape] = style



draw_color = {}

if args.viz_color is not None:
    for group, color in args.viz_color:
        draw_color[group] = color



def get_draw_color(group):
    if group in draw_color:
        return draw_color[group]
    else:
        if group in cfg['draw']:
            return cfg['draw'][group]
        else:
            return 'grey'

def get_draw_style(group, shape):
    if group in draw_style and shape in draw_style[group]:
        return draw_style[group][shape]
    else:
        return draw_style[None][shape]



anim_name, anim_data = None, None
if args.fmt == FMT_GIF_ANIM:
    anim_data = []

for li, levelfile in enumerate(args.levelfiles):
    print('processing', levelfile)

    lines = []
    max_line_len = 0

    draw_path = {}
    draw_line = {}
    draw_rect = {}
    draw_tile = {}

    def add_draw_data(draw_dict, meta):
        group = meta['group'] if 'group' in meta else '_DEFAULT'
        data = meta['data']

        if group not in draw_dict:
            draw_dict[group] = []
        draw_dict[group].append(data)

    def add_draw_data_old(draw_dict, line):
        line = line.strip()
        splt = line.split(';')
        if len(splt) == 1:
            group = '_DEFAULT'
            points_str = splt[0].strip()
        elif len(splt) == 2:
            group = splt[0].strip()
            points_str = splt[1].strip()
        else:
            raise RuntimeError('unknown DRAW format: %s' % line)

        if len(points_str) == 0:
            print(' - WARNING: empty DRAW line: %s' % line)
            points = []
        else:
            points = [tuple([float(el) for el in pt.strip().split()]) for pt in points_str.split(',')]

        if group not in draw_dict:
            draw_dict[group] = []
        draw_dict[group].append(points)

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.rstrip('\n')

            if line.startswith('META DRAW'):
                TAG = 'META DRAW PATH:'
                if line.startswith(TAG):
                    add_draw_data_old(draw_path, line[len(TAG):])
                    continue

                TAG = 'META DRAW LINE:'
                if line.startswith(TAG):
                    add_draw_data_old(draw_line, line[len(TAG):])
                    continue

                TAG = 'META DRAW RECT:'
                if line.startswith(TAG):
                    add_draw_data_old(draw_rect, line[len(TAG):])
                    continue

                TAG = 'META DRAW TILE:'
                if line.startswith(TAG):
                    add_draw_data_old(draw_tile, line[len(TAG):])
                    continue

            elif line.startswith('META REM'):
                    continue

            elif line.startswith('META'):
                meta = json.loads(line[4:])
                if meta['type'] == 'geom':
                    if meta['shape'] == 'path':
                        add_draw_data(draw_path, meta)
                    elif meta['shape'] == 'line':
                        add_draw_data(draw_line, meta)
                    elif meta['shape'] == 'rect':
                        add_draw_data(draw_rect, meta)
                    elif meta['shape'] == 'tile':
                        add_draw_data(draw_tile, meta)
                    else:
                        print(' - WARNING: unrecognized META geom: %s' % line)

            else:
                lines.append(line)
                max_line_len = max(max_line_len, len(line))

    svg = ''

    content_width = max_line_len * args.size_cell
    content_height = len(lines) * args.size_cell
    svg_width = content_width + 2 * args.padding
    svg_height = content_height + 2 * args.padding
    svg += '<svg viewBox="0 0 %d %d" version="1.1" xmlns="http://www.w3.org/2000/svg" font-family="Courier, monospace" font-size="%.2fpt">\n' % (svg_width, svg_height, args.size_font)

    pngfilename = None
    if args.background_files is not None:
        pngfilename = args.background_files[li]
    elif args.background_suffix is not None:
        pngfilename = levelfile.removesuffix(args.background_suffix) + '.png'
    elif not args.background_none:
        pngfilename = pathlib.Path(levelfile).with_suffix('.png')

    tile_image = None

    if pngfilename is not None and os.path.exists(pngfilename):
        print(' - adding png background')
        pngdata = load_b64_image(pngfilename)
        svg += '  <image x="%d" y="%d" width="%d" height="%d" href="data:image/png;base64,%s"/>\n' % (args.padding, args.padding, content_width, content_height, pngdata)

    else:
        if args.tile_image_folder is not None:
            tile_image = PIL.Image.new('RGBA', (content_width, content_height), (0, 0, 0, 0))

        tilepng = {}

        for linei, line in enumerate(lines):
            for chari, char in enumerate(line):
                if args.no_blank and char == ' ':
                    continue

                x = chari * args.size_cell + args.padding
                y = (linei + 1) * args.size_cell - 1 + args.padding

                if args.tile_image_folder is not None and char not in tilepng:
                    tilepngname = os.path.join(args.tile_image_folder, char + '.png')
                    if os.path.exists(tilepngname):
                        image = load_image(tilepngname)
                        if image.size != (args.size_cell, args.size_cell):
                            image = image.resize((args.size_cell, args.size_cell))
                        tilepng[char] = image
                    else:
                        tilepng[char] = None

                if char in tilepng and tilepng[char] is not None:
                    tile_image.paste(tilepng[char], (x - args.padding, y + 1 - args.size_cell - args.padding))

                else:
                    clr = cfg['tile'][char] if char in cfg['tile'] else 'grey'

                    custom = None
                    if char == '<':
                        char = '&lt;'
                    elif char == '>':
                        char = '&gt;'
                    elif char == '&':
                        char = '&#38;'
                    elif char in '─│┐┘└┌':
                        pth = {'─': (0.0, 0.5, 1.0, 0.5), '│': (0.5, 0.0, 0.5, 1.0), '┐': (0.5, 1.0, 0.0, 0.5), '┘': (0.0, 0.5, 0.5, 0.0), '└': (0.5, 0.0, 1.0, 0.5), '┌': (1.0, 0.5, 0.5, 1.0)}[char]
                        gz = args.size_cell
                        yo = y - gz + 1
                        char = None
                        custom = '<path d="M %.2f %.2f L %.2f %.2f L %.2f %.2f" stroke="%s" stroke-width="1" stroke-linecap="round" fill="none"/>' % (x + gz * pth[0], yo + gz * pth[1], x + gz * 0.5, yo + gz * 0.5, x + gz * pth[2], yo + gz * pth[3], clr)

                    if custom is not None:
                        svg += '  ' + custom + '\n'
                    if char is not None:
                        svg += '  <text x="%.2f" y="%.2f" dominant-baseline="middle" text-anchor="middle" fill="%s" style="fill-opacity:%.2f">%s</text>\n' % (x + 0.5 * args.size_cell, y - 0.34 * args.size_cell, clr, 1.0, char)
                    svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%.2f"/>\n' % (x, y - args.size_cell + 1, args.size_cell, args.size_cell, clr, 0.3)

    if tile_image is not None:
        pngdata = b64_image(tile_image)
        svg += '  <image x="%d" y="%d" width="%d" height="%d" href="data:image/png;base64,%s"/>\n' % (args.padding, args.padding, content_width, content_height, pngdata)

    for group, points_list in draw_tile.items():
        for points in points_list:
            tile_color = get_draw_color(group)
            tile_style = get_draw_style(group, SHAPE_TILE)

            if tile_style == RECT_NONE:
                continue

            print(' - adding tiles %s' % group)

            drawn = set()
            for rr, cc in points:
                if tile_style == RECT_BORDER:
                    sides = ([rr - 1, cc] not in points, [rr + 1, cc] not in points, [rr, cc - 1] not in points, [rr, cc + 1] not in points)
                else:
                    sides = None
                svg += svg_rect(rr, cc, 1, 1, args.padding, sides, tile_style, tile_color, drawn)

    for group, points_list in draw_rect.items():
        for points in points_list:
            rect_color = get_draw_color(group)
            rect_style = get_draw_style(group, SHAPE_RECT)

            if rect_style == RECT_NONE:
                continue

            print(' - adding rects %s' % group)

            drawn = set()
            for r1, c1, r2, c2 in points:
                svg += svg_rect(r1, c1, r2 - r1, c2 - c1, args.padding, None, rect_style, rect_color, drawn)

    for group, points_list in draw_line.items():
        for points in points_list:
            line_color = get_draw_color(group)
            line_style = get_draw_style(group, SHAPE_LINE)

            if line_style == PATH_NONE:
                continue

            print(' - adding lines %s' % group)

            if args.no_avoid:
                avoid_edges = None
            else:
                avoid_edges = [(r1, c1, r2, c2) for (r1, c1, r2, c2) in points]

            for ii, (r1, c1, r2, c2) in enumerate(points):
                svg += svg_line(r1, c1, r2, c2, args.padding, line_color, 'arc-' in line_style, avoid_edges, False, False, '-arrow' in line_style, '-point' in line_style, '-dash' in line_style, '-thick' in line_style)

    for group, points_list in draw_path.items():
        for points in points_list:
            path_color = get_draw_color(group)
            path_style = get_draw_style(group, SHAPE_PATH)

            if path_style == PATH_NONE:
                continue

            expanded_points = []
            prev_point = None
            for point in points:
                if len(point) == 0:
                    prev_point = None
                elif len(point) == 2:
                    if prev_point is not None:
                        expanded_points.append([prev_point[0], prev_point[1], point[0], point[1]])
                    prev_point = point
                else:
                    expanded_points.append(point)
                    prev_point = [point[-2], point[-1]]
            points = expanded_points

            print(' - adding path %s' % group)

            if args.no_avoid:
                avoid_edges = None
            else:
                avoid_edges = [(r1, c1, r2, c2) for (r1, c1, r2, c2) in points]

            for ii, (r1, c1, r2, c2) in enumerate(points):
                svg += svg_line(r1, c1, r2, c2, args.padding, path_color, 'arc-' in path_style, avoid_edges, ii == 0, ii + 1 == len(points), '-arrow' in path_style, '-point' in path_style, '-dash' in path_style, '-thick' in path_style)

    svg += '</svg>\n'

    if args.fmt == FMT_SVG:
        data = svg
        mode = 't'
        ext = '.svg'
    elif args.fmt == FMT_PDF:
        data = svg2pdf(svg)
        mode = 'b'
        ext = '.pdf'
    elif args.fmt == FMT_PNG:
        data = svg2png(svg, svg_width, svg_height, args.raster_scale)
        mode = 'b'
        ext = '.png'
    elif args.fmt == FMT_GIF_ANIM:
        data = None
        mode = None
        ext = None

        if anim_name is None:
            anim_name = levelfile
        anim_data.append(svg2png(svg, svg_width, svg_height, args.raster_scale))
    else:
        raise RuntimeError('unknown format for output: %s' % args.fmt)

    if args.fmt != FMT_GIF_ANIM:
        if args.stdout:
            sys.stdout.write(data)

        else:
            outfilename = str(pathlib.Path(levelfile).with_suffix('')) + args.suffix + ext
            print(' - writing', outfilename)
            outfile = open(outfilename, 'w' + mode)
            outfile.write(data)

if args.fmt == FMT_GIF_ANIM:
    outfilename = str(pathlib.Path(anim_name).with_suffix('')) + args.suffix + '.anim.gif'
    print(' - writing', outfilename)
    imgs = [PIL.Image.open(io.BytesIO(data)) for data in anim_data]

    # put all the images into one image to find a good palette
    img_meta = PIL.Image.new('RGB', (imgs[0].width, imgs[0].height * len(imgs)))
    for ii, img in enumerate(imgs):
        img_meta.paste(img, (0, imgs[0].height * ii))
    img_meta = img_meta.quantize(colors=256, dither=0)
    imgs = [img.quantize(palette=img_meta, dither=0) for img in imgs]

    # disposal=2 prevents removal of duplicate frames
    imgs[0].save(fp=outfilename, append_images=imgs[1:], save_all=True, duration=args.anim_delay, loop=0, optimize=False, disposal=2)
