import re
import sys
import numpy as np

import matplotlib.pyplot as plt
import matplotlib

class ReportGenerator:
    matplotlib.use('TkAgg')
    matplotlib.rcParams['font.size'] = 8.0
    def __init__(self):
        pass
    def draw(self, resultset):
        print(resultset.get_results())
        for r in resultset.get_results():
            fig = plt.figure()
            fig.suptitle(r.filename)
            self.draw_access_region(fig.add_subplot(2, 2, 1), r, 'Read & Write', 0)
            self.draw_access_region(fig.add_subplot(2, 2, 2), r, 'Read only', 2)
            self.draw_access_region(fig.add_subplot(2, 2, 4), r, 'Write only', 1)
        plt.show()
    def draw_access_region(self, plot, result, title = None, exclude_functions_flag = 0):
        offsets = list()
        lineoffsets = list()
        linewidths = list()
        colors = list()
        exclude_functions = list()
        if title:
            plot.set_title(title)
        if exclude_functions_flag & (1 << 0):
            exclude_functions.append('ReadContig')
        if exclude_functions_flag & (1 << 1):
            exclude_functions.append('WriteContig')
        for i in range(len(result.sequence)):
            e = result.sequence[i]
            function, rank, args = e
            if function in exclude_functions:
                continue
            if function == 'ReadContig' or function == 'WriteContig':
                offsets.append(i)
                lineoffsets.append(args['loc'] + (args['sz'])/2)
                linewidths.append(args['sz'])
                if function == 'ReadContig':
                    color_index = rank * 2 + 0
                else:
                    color_index = rank * 2 + 1
                colors.append("C{}".format(color_index))
            else:
                pass
        if len(offsets) > 0:
            plot.eventplot(positions=np.array(offsets)[:, np.newaxis],
                    lineoffsets=lineoffsets, linelengths=linewidths, orientation='vertical', colors=colors)
        else:
            return

# emulates each file
class TraceResult:
    sequence = []
    def __init__(self, filename):
        self.filename = filename
    def register(self, function, rank, kwargs):
        self.sequence.append((function, rank, kwargs))

# emulates a filesystem
class TraceResultSet:
    files = dict()
    def __init__(self):
        pass
    def register(self, filename, function, rank, **kwargs):
        if function == 'Open' or function == 'SetInfo':
            if filename not in self.files:
                self.files[filename] = TraceResult(filename)
        self.files[filename].register(function, rank, kwargs)
    def get_filenames(self):
        return list(self.files.keys())
    def get_results(self):
        return list(self.files.values())

# load and parse logs from a single text file
class LogLoader:
    def __init__(self, path):
        self.path = path
        self.results = TraceResultSet()
    def parse(self):
        ranks_buffer = dict()
        with open(self.path, 'r') as f:
            lineno = 0
            while True:
                l = f.readline()
                if not l:
                    break
                lineno += 1
                
                # parse only outputs from testfs
                m0 = re.match(r'^\[(\d+)/\d+\]', l)
                if m0:
                    rank = int(m0.group(1))
                else:
                    continue
                m1 = re.match(r'.+ADIOI_[^_]+?_(\w+?) called on ([^ ]+)\n', l)
                if m1:
                    function = m1.group(1)
                    filename = m1.group(2)
                    if function == 'ReadContig' or function == 'WriteContig':
                        # records of ReadContig or WriteContig consist from two lines
                        # these records may be mixed with other rank at mpirun -np N (N > 1)
                        # we assume the outputs of each rank are sequential
                        # and we cache records by rank (link first and latter line by rank)
                        if rank in ranks_buffer:
                            buf_function, buf_filename, buf_lineno = ranks_buffer[rank]
                            raise Exception('function {} record may be corrupted. before entry at line {}. current line is {}'.format(buf_function, buf_lineno, lineno))
                        else:
                            ranks_buffer[rank] = (function, filename, lineno)
                    else:
                        self.results.register(filename, function, rank)
                # some outputs consist from two lines
                m2 = re.match(r'.+\(buf = (.+?), loc = (\d+?), sz = (\d+?)\)$', l)
                if m2:
                    loc = int(m2.group(2))
                    sz = int(m2.group(3))
                    try:
                        buf_function, buf_filename, buf_lineno = ranks_buffer.pop(rank)
                        self.results.register(buf_filename, buf_function, rank, loc=loc, sz=sz)
                    except KeyError:
                        raise Exception('data may be corrupted at line {}'.format(lineno))

if len(sys.argv) != 2:
    print("Usage: python thisfile.py <path to logfile>")
    sys.exit(1)

ll = LogLoader(sys.argv[1])
ll.parse()
rg = ReportGenerator()
rg.draw(ll.results)

