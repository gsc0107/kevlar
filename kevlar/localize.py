#!/usr/bin/env python
#
# -----------------------------------------------------------------------------
# Copyright (c) 2017 The Regents of the University of California
#
# This file is part of kevlar (http://github.com/dib-lab/kevlar) and is
# licensed under the MIT license: see LICENSE.
# -----------------------------------------------------------------------------

from __future__ import print_function
from subprocess import Popen, PIPE
from tempfile import TemporaryFile
import sys

import kevlar
import khmer
import pysam


class KevlarBWAError(RuntimeError):
    """Raised if the delegated BWA call fails for any reason."""
    pass


class KevlarNoReferenceMatchesError(ValueError):
    """Raised if contigs have no k-mer matches against the reference."""
    pass


class KevlarVariantLocalizationError(ValueError):
    """Raised if k-mers match to mutliple locations in the reference."""
    pass


class KevlarRefrSeqNotFound(ValueError):
    """Raised if the reference sequence cannot be found."""
    pass


def get_unique_kmers(infile, ksize=31):
    """
    Grab all unique k-mers from the specified sequence file.

    The input file is expected to contain contigs in augmented FASTA format.
    The absence of annotated k-mers is not problematic, but the contigs should
    be on a single line.
    """
    ct = khmer.Counttable(ksize, 1, 1)
    kmers = set()
    instream = kevlar.open(infile, 'r')
    for record in kevlar.parse_augmented_fastx(instream):
        for kmer in ct.get_kmers(record.sequence):
            minkmer = kevlar.revcommin(kmer)
            if minkmer not in kmers:
                kmers.add(minkmer)
                yield kmer


def unique_kmer_string(infile, ksize=31):
    """Convert contigs to k-mer Fasta for BWA input."""
    output = ''
    for n, kmer in enumerate(get_unique_kmers(infile, ksize)):
        output += '>kmer{:d}\n{:s}\n'.format(n, kmer)
    return output


def get_exact_matches(infile, bwaindexfile, ksize=31):
    """
    Compute a list of exact k-mer matches using BWA MEM.

    Input should be a Fasta file containing contigs generated by
    `kevlar assemble`. This function decomposes the contigs into their
    constituent k-mers and searches for exact matches in the reference using
    `bwa mem`. This function is a generator, and yields tuples of
    (seqid, startpos) for each exact match found.
    """
    kmers = unique_kmer_string(infile, ksize)
    cmd = 'bwa mem -k {k} -T {k} {idx} -'.format(k=ksize, idx=bwaindexfile)
    cmdargs = cmd.split(' ')
    with TemporaryFile() as samfile:
        bwaproc = Popen(cmdargs, stdin=PIPE, stdout=samfile, stderr=PIPE,
                        universal_newlines=True)
        stdout, stderr = bwaproc.communicate(input=kmers)
        if bwaproc.returncode != 0:
            print(stderr, file=sys.stderr)
            raise KevlarBWAError('problem running BWA')
        samfile.seek(0)
        sam = pysam.AlignmentFile(samfile, 'r')
        for record in sam:
            if record.is_unmapped:
                continue
            seqid = sam.get_reference_name(record.reference_id)
            yield seqid, record.pos


def select_region(matchlist, maxdiff=1000, delta=100):
    """
    Given a list of match locations, select the corresponding genomic region.

    List contents should be tuples of (seqid, startpos). Returns `None` if the
    matches correspond to more than one location, as determined by sequence IDs
    or by a large difference in min and max positions.

    Returns a region in the form of a tuple (seqid, startpos, endpos), where
    startpos and endpos define a 0-based half-open interval. Bounds checking is
    performed on startpos (it is never less than 0), but no bounds checking is
    performed on endpos (this is compensated for in the `extract_region`
    function).
    """
    seqids = set([s for s, p in matchlist])
    if len(seqids) > 1:
        message = "variant matches {:d} sequence IDs".format(len(seqids))
        raise KevlarVariantLocalizationError(message)

    minpos = min([p for s, p in matchlist])
    maxpos = max([p for s, p in matchlist])
    diff = maxpos - minpos
    if diff > maxdiff:
        message = 'variant spans > {:d} bp (max {:d})''.format(diff, maxdiff)
        message += '; stubbornly refusing to continue'
        raise KevlarVariantLocalizationError(message)

    minpos = 0 if delta > minpos else minpos - delta
    maxpos += delta + 1

    return seqids.pop(), minpos, maxpos


def extract_region(refr, seqid, start, end):
    """
    Extract the specified genomic region from the provided file object.

    The start and end parameters define a 0-based half-open genomic interval.
    Bounds checking must be performed on the end parameter.
    """
    for defline, sequence in kevlar.seqio.parse_fasta(refr):
        testseqid = defline[1:].split()[0]
        if seqid == testseqid:
            if end > len(sequence):
                end = len(sequence)
            subseqid = '{}_{}-{}'.format(seqid, start, end)
            subseq = sequence[start:end]
            return subseqid, subseq
    raise KevlarRefrSeqNotFound()


def main(args):
    output = kevlar.open(args.out, 'w')
    matchgen = get_exact_matches(args.contigs, args.refr, args.ksize)
    kmer_matches = [m for m in matchgen]
    if len(kmer_matches) == 0:
        raise KevlarNoReferenceMatchesError()

    region = select_region(kmer_matches, args.max_diff, args.delta)
    seqid, start, end = region
    instream = kevlar.open(args.refr, 'r')
    subseqid, subseq = extract_region(instream, seqid, start, end)
    print('>', subseqid, '\n', subseq, sep='', file=output)
