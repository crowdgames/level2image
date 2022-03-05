import argparse, base64, json, math, os, pathlib, sys

EDGES_NONE     = 'none'
EDGES_LINE     = 'line'
EDGES_ARC      = 'arc'
EDGES_LIST     = [EDGES_NONE, EDGES_LINE, EDGES_ARC]

BLOCKS_NONE         = 'none'
BLOCKS_FILL         = 'fill'
BLOCKS_FILL_UNIQ    = 'fill-uniq'
BLOCKS_OUTLINE      = 'outline'
BLOCKS_LIST         = [BLOCKS_NONE, BLOCKS_FILL, BLOCKS_FILL_UNIQ, BLOCKS_OUTLINE]

FMT_SVG             = 'svg'
FMT_PDF             = 'pdf'
FMT_LIST            = [FMT_SVG, FMT_PDF]

parser = argparse.ArgumentParser(description='Create svg from level file.')
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')
parser.add_argument('--fontsize', type=int, help='Font size.', default=8)
parser.add_argument('--gridsize', type=int, help='Grid size.', default=10)
parser.add_argument('--cfgfile', type=str, help='Config file.')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--path-edges', type=str, choices=EDGES_LIST, help='How to display path edges, from: ' + ','.join(EDGES_LIST) + '.', default=EDGES_LINE)
parser.add_argument('--misc-edges', type=str, choices=EDGES_LIST, help='How to display misc edges, from: ' + ','.join(EDGES_LIST) + '.', default=EDGES_LINE)
parser.add_argument('--misc-blocks', type=str, choices=BLOCKS_LIST, help='How to display misc blocks, from: ' + ','.join(BLOCKS_LIST) + '.', default=BLOCKS_OUTLINE)
parser.add_argument('--edges-no-arrows', action='store_true', help='Don\'t show arrows on edges.')
parser.add_argument('--path-tiles', type=str, choices=BLOCKS_LIST, help='How to display path tiles, from: ' + ','.join(BLOCKS_LIST) + '.', default=BLOCKS_FILL)
parser.add_argument('--path-color', type=str, help='Path color.', default='orangered')
parser.add_argument('--misc-color', type=str, help='Misc color.', default='darkgoldenrod')
parser.add_argument('--no-background', action='store_true', help='Don\'t use background images if present.')
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

def svg_rect(r0, c0, rsz, csz, style, color, drawn):
    if style == BLOCKS_FILL_UNIQ and (r0, c0, rsz, csz) in drawn:
        return ''

    drawn.add((r0, c0, rsz, csz))

    x0 = c0 * args.gridsize
    y0 = r0 * args.gridsize
    xsz = max(0.01, csz * args.gridsize)
    ysz = max(0.01, rsz * args.gridsize)

    if style == BLOCKS_FILL or style == BLOCKS_FILL_UNIQ:
        style_svg = 'stroke:none;fill:%s;fill-opacity:0.3' % (color)
    else:
        style_svg = 'stroke:%s;fill:none' % (color)

    return '  <rect x="%f" y="%f" width="%f" height="%f" style="%s"/>\n' % (x0, y0, xsz, ysz, style_svg)

def svg_line(r1, c1, r2, c2, color, require_arc, arc_avoid_edges, from_circle, to_circle, to_arrow):
    if (r1, c1) == (r2, c2):
        print(' - WARNING: skipping zero-length edge: %f %f %f %f' % (r1, c1, r2, c2))
        return ''

    x1 = (c1 + 0.5) * args.gridsize
    y1 = (r1 + 0.5) * args.gridsize
    x2 = (c2 + 0.5) * args.gridsize
    y2 = (r2 + 0.5) * args.gridsize

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

    ret = ''
    if from_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x1, y1, color)
    if to_circle:
        ret += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x2, y2, color)

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

for levelfile in args.levelfiles:
    print('processing', levelfile)

    lines = []
    max_line_len = 0
    path_edges = None
    path_tiles = None
    misc_edges = None
    misc_blocks = None

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.rstrip('\n')
            if len(line) == 0:
                continue

            TAG = 'META PATH EDGES:'
            if line.startswith(TAG):
                if path_edges != None:
                    raise RuntimeError('multiple path edges found')
                path_edges = [tuple([float(el) for el in pt.strip().split()]) for pt in line[len(TAG):].split(';')]
                continue

            TAG = 'META PATH TILES:'
            if line.startswith(TAG):
                if path_tiles != None:
                    raise RuntimeError('multiple path tiles found')
                path_tiles = [tuple([float(el) for el in pt.strip().split()]) for pt in line[len(TAG):].split(';')]
                continue

            TAG = 'META MISC EDGES:'
            if line.startswith(TAG):
                if misc_edges == None:
                    misc_edges = []
                misc_edges += [tuple([float(el) for el in pt.strip().split()]) for pt in line[len(TAG):].split(';')]
                continue

            TAG = 'META MISC BLOCKS:'
            if line.startswith(TAG):
                if misc_blocks == None:
                    misc_blocks = []
                misc_blocks += [tuple([float(el) for el in pt.strip().split()]) for pt in line[len(TAG):].split(';')]
                continue

            if line.startswith('META'):
                print(' - WARNING: unrecognized META line: %s' % line)
                continue

            if line.startswith('REM'):
                continue

            lines.append(line)
            max_line_len = max(max_line_len, len(line))

    svg = ''

    svg += '<svg viewBox="0 0 %d %d" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="Courier, monospace" font-size="%dpt">\n' % (max_line_len * args.gridsize, len(lines) * args.gridsize, args.fontsize)

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
                x = chari * args.gridsize
                y = (linei + 1) * args.gridsize - 1
                clr = cfg['colors'][char] if char in cfg['colors'] else 'grey'

                if char == '<':
                    char = '&lt;'
                elif char == '>':
                    char = '&gt;'
                elif char == '&':
                    char = '&#38;'

                svg += '  <text x="%d" y="%d" fill="%s" style="fill-opacity:%f">%s</text>\n' % (x + 2, y - 1, clr, 1.0, char)
                svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%f"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, clr, 0.3)

    if path_tiles != None and args.path_tiles != BLOCKS_NONE:
        print(' - adding tiles path')

        path_color = args.path_color

        drawn = set()
        for rr, cc in path_tiles:
            svg += svg_rect(rr, cc, 1, 1, args.path_tiles, path_color, drawn)

    if misc_blocks != None and args.misc_blocks != BLOCKS_NONE:
        print(' - adding blocks misc')

        block_color = args.misc_color

        drawn = set()
        for r1, c1, r2, c2 in misc_blocks:
            svg += svg_rect(r1, c1, r2 - r1, c2 - c1, args.misc_blocks, block_color, drawn)

    if misc_edges != None and args.misc_edges != EDGES_NONE:
        print(' - adding edges misc')

        edge_color = args.misc_color
        avoid_edges = misc_edges

        skip_path_edges = set()
        if path_edges != None and args.path_edges != EDGES_NONE:
            for (r1, c1), (r2, c2) in zip(path_edges, path_edges[1:]):
                skip_path_edges.add((r1, c1, r2, c2))

        for r1, c1, r2, c2 in misc_edges:
            if (r1, c1, r2, c2) in skip_path_edges:
                continue
            
            svg += svg_line(r1, c1, r2, c2, edge_color, args.misc_edges == EDGES_ARC, avoid_edges, False, False, not args.edges_no_arrows)

    if path_edges != None and args.path_edges != EDGES_NONE:
        print(' - adding edges path')

        path_color = args.path_color
        avoid_edges = [(r1, c1, r2, c2) for ((r1, c1), (r2, c2)) in zip(path_edges, path_edges[1:])]

        for ii, ((r1, c1), (r2, c2)) in enumerate(zip(path_edges, path_edges[1:])):
            svg += svg_line(r1, c1, r2, c2, path_color, args.path_edges == EDGES_ARC, avoid_edges, ii == 0, ii + 2 == len(path_edges), not args.edges_no_arrows)

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
    else:
        raise RuntimeError('unknown format for output: %s' % args.fmt)

    if args.stdout:
        sys.stdout.write(data)

    else:
        outfilename = pathlib.Path(levelfile).with_suffix(ext)
        print(' - writing', outfilename)
        outfile = open(outfilename, 'w' + mode)
        outfile.write(data)
