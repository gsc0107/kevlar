#!/usr/bin/env python
#
# -----------------------------------------------------------------------------
# Copyright (c) 2017 The Regents of the University of California
#
# This file is part of kevlar (http://github.com/dib-lab/kevlar) and is
# licensed under the MIT license: see LICENSE.
# -----------------------------------------------------------------------------

import sys
import networkx
import khmer
import kevlar


def partition(readstream, strict=False, minabund=None, maxabund=None,
              dedup=True, gmlfile=None, logstream=sys.stderr):
    timer = kevlar.Timer()
    timer.start()

    timer.start('loadreads')
    print('[kevlar::partition] Loading reads', file=logstream)

    graph = kevlar.ReadGraph()
    graph.load(readstream, minabund=minabund, maxabund=maxabund)
    elapsed = timer.stop('loadreads')
    print('[kevlar::partition]', 'Reads loaded in {:.2f} sec'.format(elapsed),
          file=logstream)

    timer.start('buildgraph')
    mode = 'strict' if strict else 'relaxed'
    message = 'Building read graph in {:s} mode'.format(mode)
    print('[kevlar::partition]', message, file=logstream)
    graph.populate_edges(strict=strict)
    elapsed = timer.stop('buildgraph')
    print('[kevlar::partition]', 'Graph built in {:.2f} sec'.format(elapsed),
          file=logstream)

    if gmlfile:
        kevlar.to_gml(graph, gmlfile, logstream)

    timer.start('partition')
    print('[kevlar::partition] Partition readgraph', file=logstream)
    part_iter = graph.partitions(dedup, minabund, maxabund, abundfilt=True)
    for part in part_iter:
        reads = [graph.get_record(readname) for readname in list(part)]
        yield reads
    elapsed = timer.stop('partition')
    print('[kevlar::partition]',
          'Partitioning done in {:.2f} sec'.format(elapsed), file=logstream)

    total = timer.stop()
    message = 'Total time: {:.2f} seconds'.format(total)
    print('[kevlar::partition]', message, file=logstream)


def main(args):
    kevlar.mkdirp(args.outprefix, trim=True)
    readstream = kevlar.parse_augmented_fastx(kevlar.open(args.augfastq, 'r'))
    partitioner = partition(readstream, strict=args.strict,
                            minabund=args.min_abund, maxabund=args.max_abund,
                            dedup=args.dedup, gmlfile=args.gml,
                            logstream=args.logfile)
    numpart = 0
    numreads = 0
    cclog = kevlar.open(args.outprefix + '.cc.log', 'w')
    for numpart, part in enumerate(partitioner, 1):
        numreads += len(part)
        readnames = [read.name for read in part]
        print('CC', numpart, len(part), readnames, sep='\t', file=cclog)
        outfilename = '{:s}.cc{:d}.augfastq.gz'.format(args.outprefix, numpart)
        with kevlar.open(outfilename, 'w') as outfile:
            for read in part:
                kevlar.print_augmented_fastx(read, outfile)
    message = '[kevlar::partition] grouped {:d} reads'.format(numreads)
    message += ' into {:d} connected components'.format(numpart)
    print(message, file=args.logfile)
