"""
Functions for parsing comic info from filename
This should probably be re-written, but, well, it mostly works!
"""
"""
Copyright 2012-2014  Anthony Beville
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
# Some portions of this code were modified from pyComicMetaThis project
# http://code.google.com/p/pycomicmetathis/
import re
import sys
import os
try:
    from urllib.parse import unquote
except:
    from urllib import unquote

# import self.volume

def breakup_filename(fn):
    series = issue = volume = subtitle = None
    num = None
    
#    print("Re-parsing %s" % fn)
    pat = re.search(r'(.+)\s+(v|vol\.?\s*|volume\s*)(\d+)\s*-\s*(.+)$', fn, re.I)
    if pat is not None:
        series = pat.group(1)
        volume = pat.group(3)
        subtitle = pat.group(4)
        num = 1
    else:
        pat = re.search(r'(.+?) (v|vol\.?\s*|volume\s*)(\d+)\s*[-\(]+', fn, re.I)
        if pat is not None:
            series = pat.group(1)
            volume = pat.group(3)
            issue = None
            num = 2
        else:
            pat = re.search(r'(.+?) (v|vol\.?\s*|volume\s*)(\d+)\s*$', fn, re.I)
            if pat is not None:
                series = pat.group(1)
                volume = pat.group(3)
                issue = None
                num = 3
            else:
                pat = re.search(r'(.+?) (part\s*)?T?(\d+)\s*[\(\[]?of \d+[-\(]+', fn, re.I)
                if pat is not None:
                    series = pat.group(1)
                    issue = int(pat.group(3), 10)
                    num = 4
                else:
                    pat = re.search(r'(.+?) (part\s*)?T?(\d+)\s*[-\(]+', fn, re.I)
                    if pat is not None:
                        series = pat.group(1)
                        issue = int(pat.group(3), 10)
                        num = 5
                    else:
                        pat = re.search(r'(.+?) (part\s*)?T?(\d+)\s*$', fn, re.I)
                        if pat is not None:
                            series = pat.group(1)
                            issue = int(pat.group(3), 10)
                            num = 6
                        else:
                            pat = re.search(r'(.+?) (part\s*)?T?(\d+)\s*$', fn, re.I)
                            if pat is not None:
                                series = pat.group(1)
                                issue = None
                                num = 7
    
    if volume is not None and volume != '' and isinstance(volume, str):
        if volume.isdigit():
            volume = int(volume, 10)

    if issue is not None and issue != '' and isinstance(issue, str):
        if issue.isdigit():
            issue = int(issue, 10)
    
    print("Series: %s  Issue: %s   Vol: %s  Num: %s" % (series, issue, volume, num))
    return (series,issue, volume)


class FileNameParser:
    def __init__(self):
        self.series = self.issue = self.volume = None
        self.remainder = self.publisher = None

    def repl(self, m):
        return ' ' * len(m.group())

    def fixSpaces(self, string, remove_dashes=True):
        if remove_dashes:
            placeholders = ['[-_]', '  +']
        else:
            placeholders = ['[_]', '  +']
        for ph in placeholders:
            string = re.sub(ph, self.repl, string)
        return string

    def getIssueCount(self, filename, issue_end):
        count = ""
        filename = filename[issue_end:]
        # replace any name seperators with spaces
        tmpstr = self.fixSpaces(filename)
        found = False
        match = re.search('(?<=\sof\s)\d+(?=\s)', tmpstr, re.IGNORECASE)
        if match:
            count = match.group()
            found = True
        if not found:
            match = re.search('(?<=\(of\s)\d+(?=\))', tmpstr, re.IGNORECASE)
            if match:
                count = match.group()
                found = True
        count = count.lstrip("0")
        return count

    def getIssueNumber(self, filename):
        # Returns a tuple of issue number string, and start and end indexs in
        # the filename.  (The indexes will be used to split the string up for
        # further parsing)

        found = False
        issue = ''
        start = 0
        end = 0

        # first, look for multiple "--", this means it's formatted differently
        # from most:

        if "--" in filename:
            # the pattern seems to be that anything to left of the
            # first "--" is the series name followed by issue
            filename = re.sub("--.*", self.repl, filename)
        elif "__" in filename:
            # the pattern seems to be that anything to left of the
            # first "__" is the series name followed by issue
            filename = re.sub("__.*", self.repl, filename)
        filename = filename.replace("+", " ")
        # replace parenthetical phrases with spaces

        filename = re.sub("\(.*?\)", self.repl, filename)
        filename = re.sub("\[.*?\]", self.repl, filename)

        # replace any name seperators with spaces

        filename = self.fixSpaces(filename)
        # remove any "of NN" phrase with spaces (problem: this could break on
        # some titles)
        filename = re.sub("of [\d]+", self.repl, filename)

        # print u"[{0}]".format(filename)
        # we should now have a cleaned up filename version with all the words in
        # the same positions as original filename
        # make a list of each word and its position

        word_list = list()
        for m in re.finditer("\S+", filename):
            tmg = m.group(0).lower()
            if not tmg.endswith('p'):
                word_list.append( (m.group(0), m.start(), m.end()) )
        # remove the first word, since it can't be the issue number
        if len(word_list) > 1:
            word_list = word_list[1:]
        else:
            # only one word??  just bail.
            return issue, start, end
        # Now try to search for the likely issue number word in the list
        # first look for a word with "#" followed by digits with optional sufix
        # this is almost certainly the issue number
        for w in reversed(word_list):
            if re.match("#[-]?(([0-9]*\.[0-9]+|[0-9]+)(\w*))", w[0]):
                found = True
                break
        # same as above but w/o a '#', and only look at the last word in the
        # list
        if not found:
            w = word_list[-1]

            if re.match("[-]?(([0-9]*\.[0-9]+|[0-9]+)([a-oA-OQ-Zq-z_]*))", w[0]):
                found = True
        # now try to look for a # followed by any characters
        if not found:
            for w in reversed(word_list):
                if re.match("#\S+", w[0]):
                    found = True
                    break
        if not found:
            savew = None
            for w in reversed(word_list):
                pat = re.match(r"([0-9\xbd]+\.[0-9\xbd]+|[0-9\xbd]+)$", w[0])
                if pat is not None:
                    tvstr = pat.group(1)
                    if tvstr.find(u'\xbd') > -1:
                        tvstr = tvstr.replace(u'\xbd', u'.5')
                        if tvstr.count('.') == 1:
                            tva = tvstr.split('.')
                            pfx = tva[0]
                            if pfx == '':
                                pfx = '0'
                            yn = int(pfx)
                            savew = w
                            found = True
                            if (yn > 0) and (yn < 1900):
                                break
                        elif tvstr.isdigit():
                            yn = int(tvstr)
                            savew = w
                            found = True
                            if (yn > 0) and (yn < 1900):
                                break
            if savew is not None:
                w = savew
        if found:
            issue = w[0]
            start = w[1]
            end = w[2]
            if issue[0] == '#':
                issue = issue[1:]
            return issue, start, end

    def getSeriesName(self, filename, issue_start):
        # use the issue number string index to split the filename string
        if issue_start != 0:
            filename = filename[:issue_start]
        # in case there is no issue number, remove some obvious stuff
        if "--" in filename:
            # the pattern seems to be that anything to left of the first "--"
            # is the series name followed by issue
            filename = re.sub("--.*", self.repl, filename)
        elif "__" in filename:
            # the pattern seems to be that anything to left of the first "__"
            # is the series name followed by issue
            filename = re.sub("__.*", self.repl, filename)
        filename = filename.replace("+", " ")
        tmpstr = self.fixSpaces(filename, remove_dashes=False)
        series = tmpstr
        volume = ""
        # save the last word
        try:
            last_word = series.split()[-1]
        except:
            last_word = ""
        # remove any parenthetical phrases
        series = re.sub("\(.*?\)", "", series)
        # search for volume number
        match = re.search('\s([vV]|[Vv][oO][Ll]\.?\s?)(\d+)([^\d]|$)', series)
        if match:
            start = match.start()
            end = match.end()

            if (series[(end - 1)] == ' '):
                end -= 1
            series = series[0:start] + series[end:]
            volume = match.group(2)

        # if a volume wasn't found, see if the last word is a year in
        # parentheses since that's a common way to designate the volume

        if volume == "":
            # match either (YEAR), (YEAR-), or (YEAR-YEAR2)
            match = re.search("(\()(\d{4})(-(\d{4}|)|)(\))", last_word)
            if match:
                volume = match.group(2)
        series = series.strip()
        # if we don't have an issue number (issue_start==0), look
        # for hints i.e. "TPB", "one-shot", "OS", "OGN", etc that might
        # be removed to help search online
        if issue_start == 0:
            one_shot_words = ["tpb", "os", "one-shot", "ogn", "gn"]
            try:
                last_word = series.split()[-1]
                if last_word.lower() in one_shot_words:
                    series = series.rsplit(' ', 1)[0]
            except:
                pass
        return series, volume.strip()

    def getYear(self,filename, issue_end):
        filename = filename[issue_end:]
#        print "Looking in %s" %filename
        year_end = issue_end
        year = ""
        # look for four digit number with "(" ")" or "--" around it
        match = re.search('(\d\d\d\d)-\d\d-\d\d', filename)
        if match:
            year = match.group(1)
            # remove non-numerics
            year_end = match.end() + issue_end
        else:
            match = re.search('(\(\d\d\d\d\))|(--\d\d\d\d--)', filename)
            if match:
                year = match.group()
                # remove non-numerics
                year = re.sub("[^0-9]", "", year)
                year_end = match.end() + issue_end
        return year, year_end

    def getRemainder(self, filename, year, count, issue_end):
        # make a guess at where the the non-interesting stuff begins
        remainder = ""
        if "--" in filename:
            remainder = filename.split("--", 1)[1]
        elif "__" in filename:
            remainder = filename.split("__", 1)[1]
        elif issue_end != 0:
            remainder = filename[issue_end:]
        remainder = self.fixSpaces(remainder, remove_dashes=False)
        if year != "":
            remainder = remainder.replace(year, "", 1)
        if count != "":
            remainder = remainder.replace("of " + count, "", 1)
        remainder = remainder.replace("()", "")
        return remainder.strip()

    def parseFilename(self, filename):
        self.series = self.issue = self.volume = None
        # remove the path
        filename = os.path.basename(filename)
        # remove the extension
        filename = os.path.splitext(filename)[0]
        # url decode, just in case
        filename = unquote(filename)
        
        savefilename = filename
        # sometimes archives get messed up names from too many decodings
        # often url encodings will break and leave "_28" and "_29" in place
        # of "(" and ")"  see if there are a number of these, and replace them
        if filename.count("_28") > 1 and filename.count("_29") > 1:
            filename = filename.replace("_28", "(")
            filename = filename.replace("_29", ")")
        filename = re.sub(r'((\d\d\d\d)-\d\d-\d\d) (\((#[^\)]+)\))',
                          r'\4 (\2)', filename)
        trv = self.getIssueNumber(filename)
        
        use_breakup = True
        
        if not use_breakup:
        
            if trv is not None and (len(trv) == 3):
                self.issue, issue_start, issue_end = trv
                trv = self.getSeriesName(filename, issue_start)
                if trv is not None and len(trv) == 2:
                    self.series, self.volume = trv
                else:
                    print("Cannot locate series for filename: %s" % filename)
                    sys.exit(1)
                trv = self.getYear(filename, issue_end)
                if trv is not None and len(trv) > 1:
                    self.year, year_end = trv
                self.issue_count = self.getIssueCount(filename, issue_end)
                grab_end = max(issue_end, year_end)
                self.remainder = self.getRemainder(filename, self.year,
                                                   self.issue_count, grab_end)
                if filename is not None and self.remainder is not None:
                    if ('(digital)' in filename.lower()) and ('(digital)' not in self.remainder.lower()):
                        self.remainder = '{0} (digital)'.format(self.remainder)
                    
            if self.publisher is not None:
                if self.series is not None and self.publisher.lower().strip().endswith(' vol'):
                    self.series = self.series[:-4]
            if self.volume is not None and self.volume != '':
                self.volume = self.volume.lstrip('0')
                if self.volume == '':
                    self.volume = '0'
            if self.issue is not None and self.issue != "":
                if self.issue.lower() == 'tpb':
                    self.issue = ''
                else:
                    # strip off leading zeros
                    self.issue = self.issue.lstrip("0")
                    if self.issue == "":
                        self.issue = "0"
                    if self.issue[0] == ".":
                        self.issue = "0" + self.issue
        else:
            series, issue, volume = breakup_filename(savefilename)
#            print("Series: %s  Issue: %s  Volume: %s" % (series, issue, volume))
            return {'series': series, 'issue': issue, 'volume': volume}

        return {'series': self.series, 'issue': self.issue, 'volume': self.volume}
