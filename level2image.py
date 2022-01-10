import argparse, base64, json, math, os, pathlib, sys

EDGES_NONE     = 'none'
EDGES_LINE     = 'line'
EDGES_ARC      = 'arc'
EDGES_LIST     = [EDGES_NONE, EDGES_LINE, EDGES_ARC]

PATH_TILES_NONE     = 'none'
PATH_TILES_SQUARE   = 'square'
PATH_TILES_SQ_UNIQ  = 'square-uniq'
PATH_TILES_LIST     = [PATH_TILES_NONE, PATH_TILES_SQUARE, PATH_TILES_SQ_UNIQ]

FMT_SVG             = 'svg'
FMT_PDF             = 'pdf'
FMT_LIST            = [FMT_SVG, FMT_PDF]

parser = argparse.ArgumentParser(description='Create svg from level file.')
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')
parser.add_argument('--fontsize', type=int, help='Font size.', default=8)
parser.add_argument('--gridsize', type=int, help='Grid size.', default=10)
parser.add_argument('--cfgfile', type=str, help='Config file.', default='cfg-default.json')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(FMT_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--path-edges', type=str, choices=EDGES_LIST, help='How to display path edges, from: ' + ','.join(EDGES_LIST) + '.', default=EDGES_LINE)
parser.add_argument('--misc-edges', type=str, choices=EDGES_LIST, help='How to display misc edges, from: ' + ','.join(EDGES_LIST) + '.', default=EDGES_LINE)
parser.add_argument('--edges-no-arrows', action='store_true', help='Don\'t show arrows on edges.')
parser.add_argument('--path-tiles', type=str, choices=PATH_TILES_LIST, help='How to display path tiles, from: ' + ','.join(PATH_TILES_LIST) + '.', default=PATH_TILES_SQUARE)
parser.add_argument('--path-color', type=str, help='Path color.', default='orangered')
parser.add_argument('--misc-color', type=str, help='Misc color.', default='darkgoldenrod')
parser.add_argument('--no-background', action='store_true', help='Don\'t use background images if present.')
args = parser.parse_args()

if args.stdout and args.fmt != FMT_SVG:
    raise RuntimeError('can only write svg to stdout.')

with open(args.cfgfile, 'rt') as cfgfile:
    cfg = json.load(cfgfile)


def distance(ra, ca, rb, cb):
    return ((ra - rb)**2 + (ca - cb)**2)**0.5

def is_between(ra, ca, rb, cb, rc, cc):
    if (ra, ca) == (rb, cb) or (rc, cc) == (rb, cb):
        return False
    return abs(distance(ra, ca, rb, cb) + distance(rb, cb, rc, cc) - distance(ra, ca, rc, cc)) < 0.01

def svg_line(r1, c1, r2, c2, color, require_arc, arc_avoid_edges, from_circle, to_circle, to_arrow):
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

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.strip()
            if len(line) == 0:
                continue

            if line.startswith('META PATH EDGES:'):
                if path_edges != None:
                    raise RuntimeError('multiple path edges found')
                path_edges = [tuple([int(el) for el in pt.strip().split()]) for pt in line[16:].split(';')]
                continue

            if line.startswith('META PATH TILES:'):
                if path_tiles != None:
                    raise RuntimeError('multiple path tiles found')
                path_tiles = [tuple([int(el) for el in pt.strip().split()]) for pt in line[16:].split(';')]
                continue

            if line.startswith('META MISC EDGES:'):
                if misc_edges == None:
                    misc_edges = []
                misc_edges += [tuple([int(el) for el in pt.strip().split()]) for pt in line[16:].split(';')]
                continue

            if line.startswith('REM') or line.startswith('META'):
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
                if char == '>':
                    char = '&gt;'

                svg += '  <text x="%d" y="%d" fill="%s" style="fill-opacity:%f">%s</text>\n' % (x + 2, y - 1, clr, 1.0, char)

                if char != '-':
                    svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:%f"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, clr, 0.3)

    if path_tiles != None and args.path_tiles != PATH_TILES_NONE:
        print(' - adding tiles path')

        path_color = args.path_color

        drawn = set()
        for rr, cc in path_tiles:
            x = cc * args.gridsize
            y = (rr + 1) * args.gridsize - 1
            if args.path_tiles == PATH_TILES_SQUARE or (args.path_tiles == PATH_TILES_SQ_UNIQ and (x, y) not in drawn):
                svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="stroke:none;fill:%s;fill-opacity:0.3"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, path_color)
            drawn.add((x, y))

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
