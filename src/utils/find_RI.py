'''The script identifies intron retention from a BED file.
Output is written in GFF format suitable for differential
exon usage analysis using MISO.

'''

import sys
import csv

import networkx as nx
from bx.intervals import IntervalTree


class Exon(object):
    def __init__(self, chrom, start, end, transcript_id, strand):
        self.chrom = chrom
        self.start = start
        self.end = end
        self.transcript_id = transcript_id
        self.geneID = transcript_id.split('.')[0]
        self.strand = strand

    def __str__(self):
        return "%s:%d-%d" % (self.chrom, self.start, self.end)


def parse_BED(filename):
    reader = csv.reader(open(filename), dialect='excel-tab')
    for row in reader:
        chrom = row[0]
        chrom_start = int(row[1]) + 1
        transcript_id = row[3].replace(':', '-')
        strand = row[5]
        exon_sizes = [int(s) for s in row[10].split(',')]
        exon_starts = [int(s) for s in row[11].split(',')]
        if strand == '.':
            continue
        yield (chrom,
                chrom_start,
                transcript_id,
                strand,
                exon_sizes,
                exon_starts)


def get_exon_node(infile):
    for features in parse_BED(infile):
        (chrom, chrom_start, transcript_id,
                strand, exon_sizes, exon_starts) = features
        exons = []
        for i in range(len(exon_sizes)):
            start = chrom_start + exon_starts[i]
            end = start + exon_sizes[i] - 1
            exons.append(Exon(chrom, start, end, transcript_id, strand))
        yield exons, transcript_id


def add_intervals(graph, exonsDb):
    iv_tree = IntervalTree()
    for node in graph.nodes():
        exon = exonsDb[node]
        iv_tree.add_interval(exon)

    return iv_tree


def find_RI(graph, interval_tree, exonsDB):
    for edge in graph.edges():
        up, dn = edge
        up = exonsDB[up]  # upstream exon
        dn = exonsDB[dn]  # downstream exon
        intrn_ret = [[up, dn]]

        for overlap in interval_tree.find(up.start, dn.end):
            if (overlap.start == up.start and overlap.end == dn.end):
                intrn_ret.append([overlap])
        if len(intrn_ret) > 1:
            yield intrn_ret


def write_GFF(events, no_events):
    all_exons = set()
    for event in events:
        for exon in event:
            all_exons.add(exon)
    all_exons = sorted(list(all_exons), key=lambda x: x.end)

    first_exon = all_exons[0]
    last_exon = all_exons[-1]
    mrnaid = 1
    event_no = str(no_events[first_exon.geneID])
    geneID = first_exon.geneID + '.ev' + event_no
    print "%s\tRI\tgene\t%d\t%d\t.\t%s\t.\tID=%s;Name=%s" % (
            first_exon.chrom, first_exon.start, last_exon.end,
            first_exon.strand, geneID, first_exon.geneID)
    for event in events:
        event_exons = sorted([exon for exon in event],
                                                key=lambda x: x.end)
        first_exon = event_exons[0]
        last_exon = event_exons[-1]
        print "%s\tRI\tmRNA\t%d\t%d\t.\t%s\t.\tID=%s.%d;Parent=%s" % (
                        first_exon.chrom, first_exon.start, last_exon.end,
                        first_exon.strand, geneID, mrnaid, geneID)
        exonid = 1
        for exon in event_exons:
            print "%s\tRI\texon\t%d\t%d\t.\t%s\t.\tID=%s.%d.%d;Parent=%s.%d" \
                            % (exon.chrom, exon.start, exon.end,
                                exon.strand, geneID, mrnaid, exonid,
                                geneID, mrnaid)
            exonid += 1
        mrnaid += 1


def main():
    no_events = {}  # number of events in a gene
    exonsDB = {}
    infile = sys.argv[1]
    graph = nx.DiGraph()
    current_id = None
    for exons, transcript_id in get_exon_node(infile):
        new_id = transcript_id.split('.')[0]
        # print >> sys.stderr, current_id, new_id
        if not current_id:  # first gene
            for e in exons:
                exonsDB[str(e)] = e
            graph.add_path([str(e) for e in exons])
            current_id = new_id
            no_events[current_id] = 0
        else:
            if new_id != current_id:
                interval_tree = add_intervals(graph, exonsDB)
                for events in find_RI(graph, interval_tree, exonsDB):
                    no_events[current_id] += 1
                    write_GFF(events, no_events)

                graph = nx.DiGraph()
                exonsDB = {}
                current_id = new_id
                no_events[current_id] = 0

            for e in exons:
                exonsDB[str(e)] = e
            graph.add_path([str(e) for e in exons])

    interval_tree = add_intervals(graph, exonsDB)
    for events in find_RI(graph, interval_tree, exonsDB):
        no_events[current_id] += 1
        write_GFF(events, no_events)


if __name__ == '__main__':
    main()
