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

KEY_COLOR         = 'color'

FMT_SVG           = 'svg'
FMT_PDF           = 'pdf'
FMT_PNG           = 'png'
FMT_GIF_ANIM      = 'gif-anim'
FMT_LIST          = [FMT_SVG, FMT_PDF, FMT_PNG, FMT_GIF_ANIM]

parser = argparse.ArgumentParser(description='Create svg from level file.')
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')
parser.add_argument('--background', type=str, nargs='+', help='Input background files.')
parser.add_argument('--no-background', action='store_true', help='Don\'t automatically use background images if present.')
parser.add_argument('--fontsize', type=int, help='Font size.', default=8)
parser.add_argument('--gridsize', type=int, help='Grid size.', default=11)
parser.add_argument('--cfgfile', type=str, help='Config file.')
parser.add_argument('--suffix', type=str, help='Extra suffix to add to output file.', default='.out')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--viz', type=str, nargs=3, action='append', help='How to display a style, from: ' + ','.join(SHAPE_LIST) + ' and ' + ','.join(PATH_LIST) + ' or ' + ','.join(RECT_LIST) + ' or color.')
parser.add_argument('--no-viz', type=str, action='append', help='Hide a style')
parser.add_argument('--no-avoid', action='store_true', help='Don\t try to avoid previous edges on path.')
parser.add_argument('--no-blank', action='store_true', help='Don\t output blank tiles')
parser.add_argument('--tile-image-folder', type=str, help='Folder to look for tile images in.')
parser.add_argument('--padding', type=int, help='Padding around edges.', default=0)
parser.add_argument('--anim-delay', type=int, help='Frame delay for animation (in ms).', default=250)
parser.add_argument('--raster-scale', type=int, help='Amount to scale raster images by.', default=2)
args = parser.parse_args()

if args.stdout and args.fmt != FMT_SVG:
    raise RuntimeError('can only write svg to stdout')

if args.cfgfile is None:
    args.cfgfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfg-default.json')

with open(args.cfgfile, 'rt') as cfgfile:
    cfg = json.load(cfgfile)

if args.background is not None and args.no_background:
    raise RuntimeError('cannot use both --background and --no-background')

if args.background is not None and len(args.background) != len(args.levelfiles):
    raise RuntimeError('must have same number of levels and backgrounds')

if args.background is None:
    backgrounds = [None] * len(args.levelfiles)
else:
    backgrounds = args.background

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

    x0 = c0 * args.gridsize + inset + padding
    xsz = csz * args.gridsize - 2 * inset
    if xsz <= 0:
        x0 = (c0 + 0.5 * (csz - 0.01)) * args.gridsize + padding
        xsz = 0.01

    y0 = r0 * args.gridsize + inset + padding
    ysz = rsz * args.gridsize - 2 * inset
    if ysz <= 0:
        y0 = (r0 + 0.5 * (rsz - 0.01)) * args.gridsize + padding
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
    x1 = (c1 + 0.5) * args.gridsize + padding
    y1 = (r1 + 0.5) * args.gridsize + padding
    x2 = (c2 + 0.5) * args.gridsize + padding
    y2 = (r2 + 0.5) * args.gridsize + padding

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
    orthmax = 0.75 * args.gridsize
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
    file_image = PIL.Image.open(filename).convert('RGB')
    image_data = PIL.Image.new(file_image.mode, file_image.size)
    image_data.putdata(file_image.getdata())
    byte_data = io.BytesIO()
    image_data.save(byte_data, 'png')
    byte_data.flush()
    byte_data.seek(0)
    pngdata = base64.b64encode(byte_data.read()).decode('ascii')
    return pngdata



draw_viz = {}
draw_viz['default'] = {}
draw_viz['default'][SHAPE_PATH] = PATH_LINE_ARROW
draw_viz['default'][SHAPE_LINE] = PATH_LINE_ARROW
draw_viz['default'][SHAPE_RECT] = RECT_OUTLINE
draw_viz['default'][SHAPE_TILE] = RECT_FILL
draw_viz['default'][KEY_COLOR] = 'grey'

if args.viz is not None:
    for style, shape, viz in args.viz:
        if shape not in SHAPE_LIST + [KEY_COLOR]:
            raise RuntimeError('unknown shape format: %s' % shape)
        if (shape in [SHAPE_PATH, SHAPE_LINE] and viz not in PATH_LIST) or (shape in [SHAPE_RECT, SHAPE_TILE] and viz not in RECT_LIST):
            raise RuntimeError('shape and viz mismatch: %s %s' % (shape, viz))

        if style not in draw_viz:
            draw_viz[style] = {}
        draw_viz[style][shape] = viz

if args.no_viz is not None:
    for style in args.no_viz:
        draw_viz[style] = {}
        draw_viz[style][SHAPE_PATH] = PATH_NONE
        draw_viz[style][SHAPE_LINE] = PATH_NONE
        draw_viz[style][SHAPE_RECT] = RECT_NONE
        draw_viz[style][SHAPE_TILE] = RECT_NONE

def get_draw_color(style):
    if style in draw_viz and KEY_COLOR in draw_viz[style]:
        return draw_viz[style][KEY_COLOR]
    return cfg['draw'][style] if style in cfg['draw'] else 'grey'

def get_draw_viz(style, shape):
    if style not in draw_viz:
        return draw_viz['default'][shape]
    if shape not in draw_viz[style]:
        return draw_viz['default'][shape]
    return draw_viz[style][shape]



anim_name, anim_data = None, None
if args.fmt == FMT_GIF_ANIM:
    anim_data = []

for levelfile, background in zip(args.levelfiles, backgrounds):
    print('processing', levelfile)

    lines = []
    max_line_len = 0

    draw_path = {}
    draw_line = {}
    draw_rect = {}
    draw_tile = {}

    def add_draw_data(draw_dict, meta):
        style = meta['group'] if 'group' in meta else 'default'
        data = meta['data']

        if style not in draw_dict:
            draw_dict[style] = []
        draw_dict[style].append(data)

    def add_draw_data_old(draw_dict, line):
        line = line.strip()
        splt = line.split(';')
        if len(splt) == 1:
            style = 'default'
            points_str = splt[0].strip()
        elif len(splt) == 2:
            style = splt[0].strip()
            points_str = splt[1].strip()
        else:
            raise RuntimeError('unknown DRAW format: %s' % line)

        if len(points_str) == 0:
            print(' - WARNING: empty DRAW line: %s' % line)
            points = []
        else:
            points = [tuple([float(el) for el in pt.strip().split()]) for pt in points_str.split(',')]

        if style not in draw_dict:
            draw_dict[style] = []
        draw_dict[style].append(points)

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

    svg_width = max_line_len * args.gridsize + 2 * args.padding
    svg_height = len(lines) * args.gridsize + 2 * args.padding
    svg += '<svg viewBox="0 0 %f %f" version="1.1" xmlns="http://www.w3.org/2000/svg" font-family="Courier, monospace" font-size="%dpt">\n' % (svg_width, svg_height, args.fontsize)

    pngfilename = None
    if background is not None:
        pngfilename = background
    elif not args.no_background:
        pngfilename = pathlib.Path(levelfile).with_suffix('.png')

    if pngfilename is not None and os.path.exists(pngfilename):
        print(' - adding png background')
        pngdata = load_image(pngfilename)
        svg += '  <image x="0" y="0" width="%d" height="%d" href="data:image/png;base64,%s"/>\n' % (max_line_len * args.gridsize, len(lines) * args.gridsize, pngdata)

    else:
        tilepngids = {}
        tilepngmissing = {}
        for linei, line in enumerate(lines):
            for chari, char in enumerate(line):
                if args.no_blank and char == ' ':
                    continue

                x = chari * args.gridsize + args.padding
                y = (linei + 1) * args.gridsize - 1 + args.padding

                if char in tilepngids:
                    pngid, pngx, pngy = tilepngids[char]
                    svg += '  <use href="#%s" x="%d" y="%d"/>\n' % (pngid, x - pngx, y - args.gridsize + 1 - pngy)

                else:
                    tilepngdata = None
                    if args.tile_image_folder is not None and char not in tilepngmissing:
                        tilepngname = os.path.join(args.tile_image_folder, char + '.png')
                        if os.path.exists(tilepngname):
                            tilepngdata = load_image(tilepngname)
                        else:
                            tilepngmissing[char] = None

                    if tilepngdata is not None:
                        pngid = ('png%d' % len(tilepngids))
                        tilepngids[char] = (pngid, x, y - args.gridsize + 1)
                        svg += '  <image x="%d" y="%d" width="%d" height="%d" id="%s" href="data:image/png;base64,%s"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, pngid, tilepngdata)

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
                            gz = args.gridsize
                            yo = y - gz + 1
                            char = None
                            custom = '<path d="M %.2f %.2f L %.2f %.2f L %.2f %.2f" stroke="%s" stroke-width="1" stroke-linecap="round" fill="none"/>' % (x + gz * pth[0], yo + gz * pth[1], x + gz * 0.5, yo + gz * 0.5, x + gz * pth[2], yo + gz * pth[3], clr)

                        if custom is not None:
                            svg += '  ' + custom + '\n'
                        if char is not None:
                            svg += '  <text x="%.2f" y="%.2f" dominant-baseline="middle" text-anchor="middle" fill="%s" style="fill-opacity:%.2f">%s</text>\n' % (x + 0.5 * args.gridsize, y - 0.34 * args.gridsize, clr, 1.0, char)
                        svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%.2f"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, clr, 0.3)

    for style, points_list in draw_tile.items():
        for points in points_list:
            tile_color = get_draw_color(style)
            tile_viz = get_draw_viz(style, SHAPE_TILE)

            if tile_viz == RECT_NONE:
                continue

            print(' - adding tiles %s' % style)

            drawn = set()
            for rr, cc in points:
                if tile_viz == RECT_BORDER:
                    sides = ([rr - 1, cc] not in points, [rr + 1, cc] not in points, [rr, cc - 1] not in points, [rr, cc + 1] not in points)
                else:
                    sides = None
                svg += svg_rect(rr, cc, 1, 1, args.padding, sides, tile_viz, tile_color, drawn)

    for style, points_list in draw_rect.items():
        for points in points_list:
            rect_color = get_draw_color(style)
            rect_viz = get_draw_viz(style, SHAPE_RECT)

            if rect_viz == RECT_NONE:
                continue

            print(' - adding rects %s' % style)

            drawn = set()
            for r1, c1, r2, c2 in points:
                svg += svg_rect(r1, c1, r2 - r1, c2 - c1, args.padding, None, rect_viz, rect_color, drawn)

    for style, points_list in draw_line.items():
        for points in points_list:
            line_color = get_draw_color(style)
            line_viz = get_draw_viz(style, SHAPE_LINE)

            if line_viz == PATH_NONE:
                continue

            print(' - adding lines %s' % style)

            if args.no_avoid is not None:
                avoid_edges = None
            else:
                avoid_edges = [(r1, c1, r2, c2) for (r1, c1, r2, c2) in points]

            for ii, (r1, c1, r2, c2) in enumerate(points):
                svg += svg_line(r1, c1, r2, c2, args.padding, line_color, line_viz == PATH_ARC, avoid_edges, False, False, '-arrow' in line_viz, '-point' in line_viz, '-dash' in line_viz, '-thick' in line_viz)

    for style, points_list in draw_path.items():
        for points in points_list:
            path_color = get_draw_color(style)
            path_viz = get_draw_viz(style, SHAPE_PATH)

            if path_viz == PATH_NONE:
                continue

            print(' - adding path %s' % style)

            if args.no_avoid is not None:
                avoid_edges = None
            else:
                avoid_edges = [(r1, c1, r2, c2) for (r1, c1, r2, c2) in points]

            for ii, (r1, c1, r2, c2) in enumerate(points):
                svg += svg_line(r1, c1, r2, c2, args.padding, path_color, path_viz == PATH_ARC, avoid_edges, ii == 0, ii + 1 == len(points), '-arrow' in path_viz, '-point' in path_viz, '-dash' in path_viz, '-thick' in path_viz)

    svg += '</svg>\n'

    if args.fmt == FMT_SVG:
        data = svg
        mode = 't'
        ext = '.svg'
    elif args.fmt == FMT_PDF:
        import cairosvg
        data = cairosvg.svg2pdf(svg)
        mode = 'b'
        ext = '.pdf'
    elif args.fmt == FMT_PNG:
        import cairosvg
        data = cairosvg.svg2png(svg, background_color='#ffffff', parent_width=svg_width, parent_height=svg_height, output_width=svg_width*args.raster_scale, output_height=svg_height*args.raster_scale)
        mode = 'b'
        ext = '.png'
    elif args.fmt == FMT_GIF_ANIM:
        import cairosvg
        data = None
        mode = None
        ext = None

        if anim_name is None:
            anim_name = levelfile
        anim_data.append(cairosvg.svg2png(svg, background_color='#ffffff', parent_width=svg_width, parent_height=svg_height, output_width=svg_width*args.raster_scale, output_height=svg_height*args.raster_scale))
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
