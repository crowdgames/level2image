import argparse, json, math, pathlib, sys

PATH_NONE = 'none'
PATH_LINE = 'line'
PATH_ARC  = 'arc'
PATH_LIST = [PATH_NONE, PATH_LINE, PATH_ARC]

FMT_SVG   = 'svg'
FMT_PDF   = 'pdf'
FMT_LIST  = [FMT_SVG, FMT_PDF]

parser = argparse.ArgumentParser(description='Create svg from level file.')
parser.add_argument('levelfiles', type=str, nargs='+', help='Input level files.')
parser.add_argument('--fontsize', type=int, help='Font size.', default=8)
parser.add_argument('--gridsize', type=int, help='Grid size.', default=10)
parser.add_argument('--cfgfile', type=str, help='Config file.', default='cfg-default.json')
parser.add_argument('--fmt', type=str, choices=FMT_LIST, help='Output format, from: ' + ','.join(PATH_LIST) + '.', default=FMT_PDF)
parser.add_argument('--stdout', action='store_true', help='Write to stdout instead of file.')
parser.add_argument('--path', type=str, choices=PATH_LIST, help='How to display path, from: ' + ','.join(PATH_LIST) + '.', default=PATH_LINE)
parser.add_argument('--path-arrows', action='store_true', help='Show arrows on path.')
parser.add_argument('--path-color', type=str, help='Path color.', default='orangered')
args = parser.parse_args()

if args.stdout and args.fmt != FMT_SVG:
    raise RuntimeError('can only write svg to stdout.')

with open(args.cfgfile, 'rt') as cfgfile:
    cfg = json.load(cfgfile)

for levelfile in args.levelfiles:
    lines = []
    max_line_len = 0
    path = None

    with open(levelfile, 'rt') as lvl:
        for line in lvl:
            line = line.strip()
            if len(line) == 0:
                continue

            if line.startswith('META PATH '):
                path = line[10:].split(';')
                path = [tuple([int(el) for el in pt.strip().split()]) for pt in path]
                continue

            lines.append(line)
            max_line_len = max(max_line_len, len(line))

    svg = ''

    svg += '<svg viewBox="0 0 %d %d" version="1.1" xmlns="http://www.w3.org/2000/svg" font-family="Courier, monospace" font-size="%dpt">\n' % (max_line_len * args.gridsize, len(lines) * args.gridsize, args.fontsize)

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
                svg += '  <rect x="%d" y="%d" width="%d" height="%d" style="fill:%s;fill-opacity:%f"/>\n' % (x, y - args.gridsize + 1, args.gridsize, args.gridsize, clr, 0.3)

    if path != None and args.path != PATH_NONE:
        def distance(ra, ca, rb, cb):
            return ((ra - rb)**2 + (ca - cb)**2)**0.5

        def is_between(ra, ca, rb, cb, rc, cc):
            return abs(distance(ra, ca, rb, cb) + distance(rb, cb, rc, cc) - distance(ra, ca, rc, cc)) < 0.01

        path_color = args.path_color

        for ii, ((r1, c1), (r2, c2)) in enumerate(zip(path, path[1:])):
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
            midx = (x1 + x2) / 2
            midy = (y1 + y2) / 2
            curvex = midx + orthx
            curvey = midy + orthy

            if ii == 0:
                svg += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x1, y1, path_color)
            elif ii + 2 == len(path):
                svg += '  <circle cx="%.2f" cy="%.2f" r="2" stroke="none" fill="%s"/>\n' % (x2, y2, path_color)

            as_arc = (args.path == PATH_ARC)

            if not as_arc:
                for jj, (rj, cj) in enumerate(path):
                    if jj == ii or jj == ii + 1:
                        continue

                    if is_between(r1, c1, rj, cj, r2, c2):
                        as_arc = True
                        break

            if args.path_arrows:
                if as_arc:
                    adjust = distance(x1, y1, x2, y2)
                    adjust = max(0.0, min(1.0, (adjust - 10) / (50 - 10))) * 0.4 + 0.6
                    rotate = math.degrees(math.atan2(y2 - (midy + adjust * orthy), x2 - (midx + adjust * orthx)))
                else:
                    rotate = math.degrees(math.atan2(y2 - y1, x2 - x1))
                svg += '  <g transform="translate(%.2f %.2f) rotate(%.2f)"><polygon points="0 0, -4 -2, -4 2" stroke="none" fill="%s"/></g>\n' % (x2, y2, rotate, path_color)

            if as_arc:
                svg += '  <path d="M %.2f %.2f Q %.2f %.2f %.2f %.2f" stroke="%s" stroke-width="1" stroke-linecap="round" fill="none"/>\n' % (x1, y1, curvex, curvey, x2, y2, path_color)
            else:
                svg += '  <line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1" stroke-linecap="round"/>\n' % (x1, y1, x2, y2, path_color)

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
        outfile = open(outfilename, 'w' + mode)
        outfile.write(data)
