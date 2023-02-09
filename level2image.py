import argparse, base64, io, json, math, os, pathlib, sys
import PIL.Image

RECT_NONE         = 'none'
RECT_FILL         = 'fill'
RECT_FILL_UNIQ    = 'fill-uniq'
RECT_OUTLINE      = 'outline'
RECT_LIST         = [RECT_NONE, RECT_FILL, RECT_FILL_UNIQ, RECT_OUTLINE]

PATH_NONE         = 'none'
PATH_LINE         = 'line'
PATH_ARC          = 'arc'
PATH_LINE_NA      = 'line-noarrow'
PATH_ARC_NA       = 'arc-noarrow'
PATH_LIST         = [PATH_NONE, PATH_LINE, PATH_ARC, PATH_LINE_NA, PATH_ARC_NA]

FMT_SVG           = 'svg'
FMT_PDF           = 'pdf'
FMT_PNG           = 'png'
FMT_GIF_ANIM      = 'gif-anim'
FMT_LIST          = [FMT_SVG, FMT_PDF, FMT_PNG, FMT_GIF_ANIM]

parser = argparse.ArgumentParser(description='Create svg from level file.')
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')
parser.add_argument('--fontsize', type=int, help='Font size.', default=8)
parser.add_argument('--gridsize', type=int, help='Grid size.', default=11)
parser.add_argument('--cfgfile', type=str, help='Config file.')
parser.add_argument('--suffix', type=str, help='Extra suffix to add to output file.', default='out')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--viz-tile', type=str, nargs=2, action='append', help='How to display tiles for a style, from: ' + ','.join(RECT_LIST) + '.')
parser.add_argument('--viz-rect', type=str, nargs=2, action='append', help='How to display rects for a style, from: ' + ','.join(RECT_LIST) + '.')
parser.add_argument('--viz-path', type=str, nargs=2, action='append', help='How to display paths for a style, from: ' + ','.join(PATH_LIST) + '.')
parser.add_argument('--no-background', action='store_true', help='Don\'t use background images if present.')
parser.add_argument('--padding', type=int, help='Padding around edges.', default=0)
parser.add_argument('--anim-delay', type=int, help='Frame delay for animation (in ms).', default=250)
args = parser.parse_args()

if args.stdout and args.fmt != FMT_SVG:
    raise RuntimeError('can only write svg to stdout.')

if args.cfgfile == None:
    args.cfgfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfg-default.json')

with open(args.cfgfile, 'rt') as cfgfile:
    cfg = json.load(cfgfile)


def distance(ra, ca, rb, cb):
    return ((ra - rb)**2 + (ca - cb)**2)**0.5

def is_between(ra, ca, rb, cb, rc, cc):
    if (ra, ca) == (rb, cb) or (rc, cc) == (rb, cb):
        return False
    return abs(distance(ra, ca, rb, cb) + distance(rb, cb, rc, cc) - distance(ra, ca, rc, cc)) < 0.01

def svg_rect(r0, c0, rsz, csz, padding, style, color, drawn):
    if (rsz, csz) == (0, 0):
        print(' - WARNING: skipping zero-size rect: %f %f %f %f' % (r0, c0, rsz, csz))
        return ''

    if style == RECT_FILL_UNIQ and (r0, c0, rsz, csz) in drawn:
        return ''

    drawn.add((r0, c0, rsz, csz))

    if style == RECT_FILL or style == RECT_FILL_UNIQ:
        style_svg = 'stroke:none;fill:%s;fill-opacity:0.3' % (color)
        inset = 0
    else:
        style_svg = 'stroke:%s;fill:none' % (color)
        inset = 0.5

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

    return '  <rect x="%f" y="%f" width="%f" height="%f" style="%s"/>\n' % (x0, y0, xsz, ysz, style_svg)

def svg_line(r1, c1, r2, c2, padding, color, require_arc, arc_avoid_edges, from_circle, to_circle, to_arrow):
    x1 = (c1 + 0.5) * args.gridsize + padding
    y1 = (r1 + 0.5) * args.gridsize + padding
    x2 = (c2 + 0.5) * args.gridsize + padding
    y2 = (r2 + 0.5) * args.gridsize + padding

    ret = ''
    if from_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x1, y1, color)
    if to_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x2, y2, color)

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
    if not as_arc and arc_avoid_edges:
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

    if to_arrow:
        if as_arc:
            adjust = distance(x1, y1, x2, y2)
            adjust = max(0.0, min(1.0, (adjust - 10) / (50 - 10))) * 0.4 + 0.6
            rotate = math.degrees(math.atan2(y2 - (midy + adjust * orthy), x2 - (midx + adjust * orthx)))
        else:
            rotate = math.degrees(math.atan2(y2 - y1, x2 - x1))
        ret += '  <g transform="translate(%.2f %.2f) rotate(%.2f)"><polygon points="0 0, -4 -2, -4 2" stroke="none" fill="%s"/></g>\n' % (x2, y2, rotate, color)

    if as_arc:
        ret += '  <path d="M %.2f %.2f Q %.2f %.2f %.2f %.2f" stroke="%s" stroke-width="1" stroke-linecap="round" fill="none"/>\n' % (x1, y1, curvex, curvey, x2, y2, color)
    else:
        ret += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1" stroke-linecap="round"/>\n' % (x1, y1, x2, y2, color)

    return ret



draw_viz_tile = {}
draw_viz_tile['default'] = RECT_FILL

draw_viz_rect = {}
draw_viz_rect['default'] = RECT_OUTLINE

draw_viz_path = {}
draw_viz_path['default'] = PATH_LINE

if args.viz_tile != None:
    for style, viz in args.viz_tile:
        if viz not in RECT_LIST:
            raise RuntimeError('unknown viz format: %s' % viz)
        draw_viz_tile[style] = viz

if args.viz_rect != None:
    for style, viz in args.viz_rect:
        if viz not in RECT_LIST:
            raise RuntimeError('unknown viz format: %s' % viz)
        draw_viz_rect[style] = viz

if args.viz_path != None:
    for style, viz in args.viz_path:
        if viz not in PATH_LIST:
            raise RuntimeError('unknown viz format: %s' % viz)
        draw_viz_path[style] = viz

def get_draw_color(style):
    return cfg['draw'][style] if style in cfg['draw'] else 'grey'

def get_draw_viz_tile(style):
    if style not in draw_viz_tile:
        return draw_viz_tile['default']
    return draw_viz_tile[style]

def get_draw_viz_rect(style):
    if style not in draw_viz_rect:
        return draw_viz_rect['default']
    return draw_viz_rect[style]

def get_draw_viz_path(style):
    if style not in draw_viz_path:
        return draw_viz_path['default']
    return draw_viz_path[style]



anim_name, anim_data = None, None
if args.fmt == FMT_GIF_ANIM:
    anim_data = []

for levelfile in args.levelfiles:
    print('processing', levelfile)

    lines = []
    max_line_len = 0

    draw_path = {}
    draw_rects = {}
    draw_tiles = {}

    def add_draw_data(draw_dict, allow_breaks, line):
        splt = line.split('-')
        if len(splt) == 1:
            style = 'default'
            line = splt[0]
        elif len(splt) == 2:
            style = splt[0].strip()
            line = splt[1]
        else:
            raise RuntimeError('unknown DRAW format: %s' % line)

        if allow_breaks:
            points = []
            point_lines = line.split(';')
            for point_line in point_lines:
                points.append([tuple([float(el) for el in pt.strip().split()]) for pt in point_line.split(',')])
        else:
            points = [tuple([float(el) for el in pt.strip().split()]) for pt in line.split(',')]

        if style not in draw_dict:
            draw_dict[style] = []
        draw_dict[style].append(points)

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.rstrip('\n')

            TAG = 'DRAW PATH:'
            if line.startswith(TAG):
                add_draw_data(draw_path, True, line[len(TAG):])
                continue

            TAG = 'DRAW RECTS:'
            if line.startswith(TAG):
                add_draw_data(draw_rects, False, line[len(TAG):])
                continue

            TAG = 'DRAW TILES:'
            if line.startswith(TAG):
                add_draw_data(draw_tiles, False, line[len(TAG):])
                continue

            if line.startswith('DRAW'):
                print(' - WARNING: unrecognized DRAW line: %s' % line)
                continue

            if line.startswith('REM'):
                continue

            lines.append(line)
            max_line_len = max(max_line_len, len(line))

    svg = ''

    svg_width = max_line_len * args.gridsize + 2 * args.padding
    svg_height = len(lines) * args.gridsize + 2 * args.padding
    svg += '<svg viewBox="0 0 %f %f" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="Courier, monospace" font-size="%dpt">\n' % (svg_width, svg_height, args.fontsize)

    pngdata = None

    if not args.no_background:
        pngfilename = pathlib.Path(levelfile).with_suffix('.png')
        if os.path.exists(pngfilename):
            print(' - adding png background')
            with open(pngfilename, 'rb') as pngfile:
                pngdata = base64.b64encode(pngfile.read()).decode('ascii')

    if pngdata:
        svg += '  <image width="%d" height="%d" xlink:href="data:image/png;base64,%s"/>\n' % (max_line_len * args.gridsize, len(lines) * args.gridsize, pngdata)

    else:
        for linei, line in enumerate(lines):
            for chari, char in enumerate(line):
                x = chari * args.gridsize + args.padding
                y = (linei + 1) * args.gridsize - 1 + args.padding
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

                if custom != None:
                    svg += '  ' + custom + '\n'
                if char != None:
                    svg += '  <text x="%f" y="%f" dominant-baseline="middle" text-anchor="middle" fill="%s" style="fill-opacity:%f">%s</text>\n' % (x + 0.5 * args.gridsize, y - 0.34 * args.gridsize, clr, 1.0, char)
                svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%f"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, clr, 0.3)

    for style, points_list in draw_tiles.items():
        for points in points_list:
            print(' - adding tiles %s' % style)

            tile_color = get_draw_color(style)
            tile_viz = get_draw_viz_tile(style)

            drawn = set()
            for rr, cc in points:
                svg += svg_rect(rr, cc, 1, 1, args.padding, tile_viz, tile_color, drawn)

    for style, points_list in draw_rects.items():
        for points in points_list:
            print(' - adding rects %s' % style)

            rect_color = get_draw_color(style)
            rect_viz = get_draw_viz_rect(style)

            drawn = set()
            for r1, c1, r2, c2 in points:
                svg += svg_rect(r1, c1, r2 - r1, c2 - c1, args.padding, rect_viz, rect_color, drawn)

    for style, points_list in draw_path.items():
        for points in points_list:
            print(' - adding path %s' % style)

            path_color = get_draw_color(style)
            path_viz = get_draw_viz_path(style)

            avoid_edges = []
            for pts in points:
                pt_pairs = list(zip(pts, pts[1:]))
                for (r1, c1), (r2, c2) in pt_pairs:
                    avoid_edges.append((r1, c1, r2, c2))

            for jj, pts in enumerate(points):
                pt_pairs = list(zip(pts, pts[1:]))
                for ii, ((r1, c1), (r2, c2)) in enumerate(pt_pairs):
                    is_first = (jj == 0) and (ii == 0)
                    is_last = (jj + 1 == len(points)) and (ii + 1 == len(pt_pairs))
                    svg += svg_line(r1, c1, r2, c2, args.padding, path_color, path_viz == PATH_ARC, avoid_edges, is_first, is_last, '-noarrow' not in path_viz)

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
        data = cairosvg.svg2png(svg, background_color='#ffffff', parent_width=svg_width, parent_height=svg_height, output_width=svg_width*2, output_height=svg_height*2)
        mode = 'b'
        ext = '.png'
    elif args.fmt == FMT_GIF_ANIM:
        import cairosvg
        data = None
        mode = None
        ext = None

        if anim_name == None:
            anim_name = levelfile
        anim_data.append(cairosvg.svg2png(svg, background_color='#ffffff', parent_width=svg_width, parent_height=svg_height, output_width=svg_width*2, output_height=svg_height*2))
    else:
        raise RuntimeError('unknown format for output: %s' % args.fmt)

    if args.fmt != FMT_GIF_ANIM:
        if args.stdout:
            sys.stdout.write(data)

        else:
            outfilename = pathlib.Path(levelfile).with_suffix('.' + args.suffix + ext)
            print(' - writing', outfilename)
            outfile = open(outfilename, 'w' + mode)
            outfile.write(data)

if args.fmt == FMT_GIF_ANIM:
    outfilename = pathlib.Path(anim_name).with_suffix('.' + args.suffix + '.anim.gif')
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
