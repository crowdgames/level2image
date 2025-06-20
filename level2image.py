import argparse, base64, io, json, math, os, pathlib, sys
import PIL.Image

RECT_NONE           = 'none'
RECT_FILL           = 'fill'
RECT_FILL_UNIQ      = 'fill-uniq'
RECT_HATCH          = 'hatch'
RECT_BACKHATCH      = 'backhatch'
RECT_OUTLINE        = 'outline'
RECT_OUTLINE_THICK  = 'outline-thick'
RECT_BORDER         = 'border'
RECT_BORDER_THICK   = 'border-thick'
RECT_LIST           = [RECT_NONE, RECT_FILL, RECT_FILL_UNIQ, RECT_HATCH, RECT_BACKHATCH, RECT_OUTLINE, RECT_OUTLINE_THICK, RECT_BORDER, RECT_BORDER_THICK]

PATH_NONE           = 'none'
PATH_LINE           = 'line'
PATH_ARC            = 'arc'
PATH_LINE_POINT     = 'line-point'
PATH_ARC_POINT      = 'arc-point'
PATH_LINE_ARROW     = 'line-arrow'
PATH_ARC_ARROW      = 'arc-arrow'
PATH_LINE_DASH      = 'line-dash'
PATH_ARC_DASH       = 'arc-dash'
PATH_LINE_THICK     = 'line-thick'
PATH_ARC_THICK      = 'arc-thick'
PATH_LIST           = [PATH_NONE, PATH_LINE, PATH_ARC, PATH_LINE_POINT, PATH_ARC_POINT, PATH_LINE_ARROW, PATH_ARC_ARROW, PATH_LINE_DASH, PATH_ARC_DASH, PATH_LINE_THICK, PATH_ARC_THICK]

SHAPE_PATH          = 'path'
SHAPE_LINE          = 'line'
SHAPE_TILE          = 'tile'
SHAPE_RECT          = 'rect'
SHAPE_LIST          = [SHAPE_PATH, SHAPE_LINE, SHAPE_TILE, SHAPE_RECT]

FMT_SVG             = 'svg'
FMT_PDF             = 'pdf'
FMT_PNG             = 'png'
FMT_GIF_ANIM        = 'gif-anim'
FMT_LIST            = [FMT_SVG, FMT_PDF, FMT_PNG, FMT_GIF_ANIM]

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

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument('--blank-none', action='store_true', help='Don\'t output blank tiles.')
group.add_argument('--blank-color', type=str, help='Use solid color for blank tiles.')

parser.add_argument('--backstage-color', type=str, help='Add a solid color behind the background.')
parser.add_argument('--font-scale', type=float, help='Amount to scale cell size by to get font size.', default=0.7)
parser.add_argument('--font-yadjust', type=float, help='Amount to adjust y position of text in cell.', default=0.12)
parser.add_argument('--cell-size', type=int, help='Cell size.', default=11)
parser.add_argument('--cfgfile', type=str, help='Config file.')
parser.add_argument('--suffix', type=str, help='Extra suffix to add to output file.', default='.out')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--viz', type=str, nargs='+', action=GroupShapeStyleAction, help='How to display the group GROUP; SHAPE from: ' + ','.join(SHAPE_LIST) + '; STYLE from: ' + ','.join(PATH_LIST) + ' or ' + ','.join(RECT_LIST) + '.')
parser.add_argument('--viz-hide', type=str, metavar='GROUP', action='append', help='Hide a group.')
parser.add_argument('--viz-none', action='store_true', help='Hide all groups other than those displayed.')
parser.add_argument('--viz-color', type=str, nargs=2, metavar=('GROUP', 'COLOR'), action='append', help='Which color to display a group.')
parser.add_argument('--no-avoid', action='store_true', help='Don\'t try to avoid previous edges on path.')
parser.add_argument('--tile-image-folder', type=str, help='Folder to look for tile images in.')
parser.add_argument('--tile-text', action='store_true', help='Always show tile text.')
parser.add_argument('--padding', type=int, help='Padding around edges.', default=0)
parser.add_argument('--anim-delay', type=int, help='Frame delay for animation (in ms).', default=250)
parser.add_argument('--raster-scale', type=int, help='Amount to scale raster images by.', default=2)

# Arguments for multiple levels in one image.
parser.add_argument('--montage', type=int, nargs=4, metavar=('MAX_X', 'MAX_Y', 'PAD_X', 'PAD_Y'), help='Put multiple levels in one image; MAX_X: number of levels per row or -1 for unlimited; MAX_Y: number of levels per column or -1 for unlimited; PAD_X: padding between levels on each row; PAD_Y: padding between levels on each column.')

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

def svg_rect(r0, c0, rsz, csz, xoff, yoff, sides, style, color, drawn):
    if (rsz, csz) == (0, 0):
        print(' - WARNING: skipping zero-size rect: %f %f %f %f' % (r0, c0, rsz, csz))
        return ''

    if style in [RECT_FILL_UNIQ, RECT_HATCH, RECT_BACKHATCH] and (r0, c0, rsz, csz) in drawn:
        return ''

    drawn.add((r0, c0, rsz, csz))

    if style in [RECT_FILL, RECT_FILL_UNIQ]:
        style_svg = 'stroke:none;fill:%s;fill-opacity:0.3' % (color)
        inset = 0
    elif style in [RECT_HATCH, RECT_BACKHATCH]:
        style_svg = 'stroke:%s;stroke-width:1.0;fill:none' % (color)
        inset = 0.0
    elif style in [RECT_OUTLINE]:
        style_svg = 'stroke:%s;fill:none' % (color)
        inset = 0.5
    elif style in [RECT_OUTLINE_THICK]:
        style_svg = 'stroke:%s;stroke-width:2.0;fill:none' % (color)
        inset = 1.0
    elif style in [RECT_BORDER]:
        style_svg = 'stroke:%s;stroke-width:1.5;fill:none' % (color)
        inset = 0
    elif style in [RECT_BORDER_THICK]:
        style_svg = 'stroke:%s;stroke-width:3.0;fill:none' % (color)
        inset = 0
    else:
        raise RuntimeError('unknown style: %s' % style)

    x0 = c0 * args.cell_size + inset + xoff
    xsz = csz * args.cell_size - 2 * inset
    if xsz <= 0:
        x0 = (c0 + 0.5 * (csz - 0.01)) * args.cell_size + xoff
        xsz = 0.01

    y0 = r0 * args.cell_size + inset + yoff
    ysz = rsz * args.cell_size - 2 * inset
    if ysz <= 0:
        y0 = (r0 + 0.5 * (rsz - 0.01)) * args.cell_size + yoff
        ysz = 0.01

    if style in [RECT_HATCH, RECT_BACKHATCH]:
        if style == RECT_HATCH:
            coords = [(0.5, 0.0, 0.0, 0.5), (1.0, 0.0, 0.0, 1.0), (1.0, 0.5, 0.5, 1.0)]
        else:
            coords = [(0.5, 0.0, 1.0, 0.5), (0.0, 0.0, 1.0, 1.0), (0.0, 0.5, 0.5, 1.0)]
        ret = ''
        for xa, ya, xb, yb in coords:
            ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" style="%s" stroke-linecap="square"/>\n' % (x0 + xa * xsz, y0 + ya * ysz, x0 + xb * xsz, y0 + yb * ysz, style_svg)
        return ret
    elif style in [RECT_BORDER, RECT_BORDER_THICK]:
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

def svg_line(r1, c1, r2, c2, xoff, yoff, color, require_arc, arc_avoid_edges, from_circle, to_circle, to_arrow, to_point, dash, thick):
    x1 = (c1 + 0.5) * args.cell_size + xoff
    y1 = (r1 + 0.5) * args.cell_size + yoff
    x2 = (c2 + 0.5) * args.cell_size + xoff
    y2 = (r2 + 0.5) * args.cell_size + yoff

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
    orthmax = 0.75 * args.cell_size
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



draw_order = []

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
            shape_order = SHAPE_LIST
        elif shape in SHAPE_LIST:
            if style is None:
                style = DRAW_STYLE_DEFAULT[shape]
            shape_to_style = {shape:style}
            shape_order = [shape]
        else:
            raise RuntimeError('unknown shape: %s' % shape)

        for shape, style in shape_to_style.items():
            if (shape in [SHAPE_PATH, SHAPE_LINE] and style not in PATH_LIST) or (shape in [SHAPE_RECT, SHAPE_TILE] and style not in RECT_LIST):
                raise RuntimeError('shape and style mismatch: %s %s' % (shape, style))

            draw_style[group][shape] = style

        for shape in shape_order:
            draw_order = [elem for elem in draw_order if elem != (group, shape)]
            draw_order.append((group, shape))



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

inner_svg = ''
offset_x = args.padding
offset_y = args.padding
svg_width = args.padding
svg_height = args.padding
lvlxi = 0
lvlyi = 0

tilepng = {}

for li, levelfile in enumerate(args.levelfiles):
    print('processing', levelfile)

    lines = []
    max_line_len = 0

    draw_data = []

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.rstrip('\n')

            if line.startswith('META'):
                meta = json.loads(line[4:])
                if meta['type'] == 'geom':
                    if meta['shape'] in SHAPE_LIST:
                        draw_data.append((meta['group'], meta['shape'], meta['data']))
                    else:
                        print(' - WARNING: unrecognized META geom: %s' % line)

            else:
                lines.append(line)
                max_line_len = max(max_line_len, len(line))

    draw_data_order = []
    for ogroup, oshape in draw_order:
        new_draw_data = []
        for meta in draw_data:
            mgroup, mshape, mpoints = meta
            if (mgroup, mshape) == (ogroup, oshape):
                draw_data_order.append(meta)
            else:
                new_draw_data.append(meta)
        draw_data = new_draw_data
    draw_data = draw_data + draw_data_order



    level_width = max_line_len * args.cell_size
    level_height = len(lines) * args.cell_size
    if args.montage is None:
        inner_svg = ''
        offset_x = args.padding
        offset_y = args.padding
        svg_width = args.padding + level_width
        svg_height = args.padding + level_height



    pngfilename = None
    if args.background_files is not None:
        pngfilename = args.background_files[li]
    elif args.background_suffix is not None:
        pngfilename = levelfile.removesuffix(args.background_suffix) + '.png'
    elif not args.background_none:
        pngfilename = pathlib.Path(levelfile).with_suffix('.png')

    tile_image = None
    text_svg = None

    added_background = False
    if pngfilename is not None and os.path.exists(pngfilename):
        print(' - adding background image')
        pngdata = load_b64_image(pngfilename)
        inner_svg += '  <image x="%d" y="%d" width="%d" height="%d" href="data:image/png;base64,%s"/>\n' % (offset_x, offset_y, level_width, level_height, pngdata)
        added_background = True

    if not added_background or args.tile_image_folder is not None or args.tile_text:
        if args.tile_image_folder is not None:
            tile_image = PIL.Image.new('RGBA', (level_width, level_height), (0, 0, 0, 0))

        for linei, line in enumerate(lines):
            for chari, char in enumerate(line):
                inner_x = chari * args.cell_size
                inner_y = (linei + 1) * args.cell_size - 1
                x = inner_x + offset_x
                y = inner_y + offset_y

                if char == ' ':
                    if args.blank_none:
                        continue
                    if args.blank_color is not None:
                        text_svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%.2f"/>\n' % (x, y - args.cell_size + 1, args.cell_size, args.cell_size, args.blank_color, 1.0)
                        continue

                if args.tile_image_folder is not None and char not in tilepng:
                    tilepngname = os.path.join(args.tile_image_folder, char + '.png')
                    if os.path.exists(tilepngname):
                        image = load_image(tilepngname)
                        if image.size != (args.cell_size, args.cell_size):
                            image = image.resize((args.cell_size, args.cell_size))
                        tilepng[char] = image
                    else:
                        tilepng[char] = None

                added_tile_image = False
                if char in tilepng and tilepng[char] is not None:
                    tile_image.paste(tilepng[char], (inner_x, inner_y - args.cell_size + 1))
                    added_tile_image = True

                if not added_tile_image or args.tile_text:
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
                        gz = args.cell_size
                        yo = y - gz + 1
                        char = None
                        custom = '<path d="M %.2f %.2f L %.2f %.2f L %.2f %.2f" stroke="%s" stroke-width="1" stroke-linecap="round" fill="none"/>' % (x + gz * pth[0], yo + gz * pth[1], x + gz * 0.5, yo + gz * 0.5, x + gz * pth[2], yo + gz * pth[3], clr)

                    if text_svg is None:
                        text_svg = ''

                    if custom is not None:
                        text_svg += '  ' + custom + '\n'
                    if char is not None:
                        text_svg += '  <text x="%.2f" y="%.2f" dominant-baseline="middle" text-anchor="middle" fill="%s" style="fill-opacity:%.2f">%s</text>\n' % (x + 0.5 * args.cell_size, y - (0.5 - args.font_yadjust) * args.cell_size, clr, 1.0, char)
                    text_svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%.2f"/>\n' % (x, y - args.cell_size + 1, args.cell_size, args.cell_size, clr, 0.3)

    if tile_image is not None:
        print(' - adding tile images')
        pngdata = b64_image(tile_image)
        inner_svg += '  <image x="%d" y="%d" width="%d" height="%d" href="data:image/png;base64,%s"/>\n' % (offset_x, offset_y, level_width, level_height, pngdata)

    if text_svg is not None:
        print(' - adding tile text')
        inner_svg += text_svg

    for group, shape, points in draw_data:
        if shape == SHAPE_TILE:
            tile_color = get_draw_color(group)
            tile_style = get_draw_style(group, SHAPE_TILE)

            if tile_style == RECT_NONE:
                continue

            print(' - adding tiles %s' % group)

            drawn = set()
            for rr, cc in points:
                if tile_style in [RECT_BORDER, RECT_BORDER_THICK]:
                    sides = ([rr - 1, cc] not in points, [rr + 1, cc] not in points, [rr, cc - 1] not in points, [rr, cc + 1] not in points)
                else:
                    sides = None
                inner_svg += svg_rect(rr, cc, 1, 1, offset_x, offset_y, sides, tile_style, tile_color, drawn)

        elif shape == SHAPE_RECT:
            rect_color = get_draw_color(group)
            rect_style = get_draw_style(group, SHAPE_RECT)

            if rect_style == RECT_NONE:
                continue

            print(' - adding rects %s' % group)

            drawn = set()
            for r1, c1, r2, c2 in points:
                inner_svg += svg_rect(r1, c1, r2 - r1, c2 - c1, offset_x, offset_y, None, rect_style, rect_color, drawn)

        elif shape == SHAPE_LINE:
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
                inner_svg += svg_line(r1, c1, r2, c2, offset_x, offset_y, line_color, 'arc-' in line_style, avoid_edges, False, False, '-arrow' in line_style, '-point' in line_style, '-dash' in line_style, '-thick' in line_style)

        elif shape == SHAPE_PATH:
            path_color = get_draw_color(group)
            path_style = get_draw_style(group, SHAPE_PATH)

            if path_style == PATH_NONE:
                continue

            solitary_points = []
            edges = []

            prev_point_connected = False
            prev_point = None
            for point in points:
                if point is None or len(point) == 0:
                    if prev_point is not None and not prev_point_connected:
                        solitary_points.append(prev_point)
                    prev_point_connected = False
                    prev_point = None
                elif len(point) == 2:
                    if prev_point is not None:
                        edges.append([prev_point[0], prev_point[1], point[0], point[1]])
                    prev_point_connected = prev_point is not None
                    prev_point = point
                elif len(point) == 4:
                    edges.append(point)
                    prev_point_connected = True
                    prev_point = [point[-2], point[-1]]
                elif len(point) == 6:
                    fr, fc, tr, tc, pwtr, pwtc = point
                    edges.append([fr, fc, pwtr, pwtc])
                    edges.append([tr - (pwtr - fr), tc - (pwtc - fc), tr, tc])
                    prev_point_connected = True
                    prev_point = [tr, tc]
                else:
                    raise RuntimeError('unknown point type: %s' % str(point))

            if prev_point is not None and not prev_point_connected:
                solitary_points.append(prev_point)

            print(' - adding path %s' % group)
            for r1, c1 in solitary_points:
                print(' - WARNING: skipping solitary path point: %f %f' % (r1, c1))

            if args.no_avoid:
                avoid_edges = None
            else:
                avoid_edges = [(r1, c1, r2, c2) for (r1, c1, r2, c2) in edges]

            for ii, (r1, c1, r2, c2) in enumerate(edges):
                inner_svg += svg_line(r1, c1, r2, c2, offset_x, offset_y, path_color, 'arc-' in path_style, avoid_edges, ii == 0, ii + 1 == len(edges), '-arrow' in path_style, '-point' in path_style, '-dash' in path_style, '-thick' in path_style)

    finish_svg = True
    if args.montage is not None:
        MAX_X, MAX_Y, PAD_X, PAD_Y = args.montage
        finish_svg = False
        if lvlxi == 0:
            # Adding a new row adds to height.
            svg_height += level_height
        # Add to row
        lvlxi += 1
        offset_x += level_width + PAD_X
        if lvlyi == 0:
            # Adding to first row adds to width.
            svg_width += level_width
        if li == len(args.levelfiles) - 1:
            # Print at the last level regardless.
            finish_svg = True
        elif lvlxi == MAX_X:
            # Add a new row; reset x offset and increase y offset.
            lvlxi = 0
            offset_x = args.padding
            lvlyi += 1
            offset_y += level_height + PAD_Y
            if lvlyi == MAX_Y:
                # Start a new svg entirely.
                lvlyi = 0
                offset_y = args.padding
                finish_svg = True
            else:
                # Prep for new row.
                svg_height += PAD_Y
        elif lvlyi == 0:
            # Prep for adding to row.
            svg_width += PAD_X

    if not finish_svg:
        continue

    svg = ''
    svg_width += args.padding
    svg_height += args.padding
    svg += '<svg viewBox="0 0 %d %d" version="1.1" xmlns="http://www.w3.org/2000/svg" font-family="Courier, monospace" font-size="%.2fpt">\n' % (svg_width, svg_height, args.font_scale * args.cell_size)
    if args.backstage_color is not None:
        svg += '  <rect width="100%%" height="100%%" fill="%s"/>' % args.backstage_color
    svg += inner_svg
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

    if args.montage is not None:
        # Reset for next svg.
        inner_svg = ''
        svg_width = args.padding
        svg_height = args.padding
        offset_x = args.padding
        offset_y = args.padding

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
