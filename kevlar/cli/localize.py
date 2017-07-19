#!/usr/bin/env python
#
# -----------------------------------------------------------------------------
# Copyright (c) 2017 The Regents of the University of California
#
# This file is part of kevlar (http://github.com/dib-lab/kevlar) and is
# licensed under the MIT license: see LICENSE.
# -----------------------------------------------------------------------------


def subparser(subparsers):
    subparser = subparsers.add_parser('localize')
    subparser.add_argument('-x', '--max-diff', type=int, metavar='X',
                           default=1000, help='span of all k-mer starting '
                           'positions should not exceed X bp')
    subparser.add_argument('-d', '--delta', type=int, metavar='D',
                           default=100, help='retrieve the genomic interval '
                           'from the reference by extending beyond the span '
                           'of all k-mer starting positions by D bp')
    subparser.add_argument('-o', '--out', metavar='FILE', default='-',
                           help='output file; default is terminal (stdout)')
    subparser.add_argument('-k', '--ksize', type=int, metavar='K', default=31,
                           help='k-mer size; default is 31')
    subparser.add_argument('contigs', help='assembled reads in Fasta format')
    subparser.add_argument('refr', help='BWA indexed reference genome')