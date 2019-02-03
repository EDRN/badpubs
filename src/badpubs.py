#!/usr/bin/env python
# encoding: utf-8
# 
# badpubs - find “bad” publications in DMCC's publications RDF feed
# 
# Usage: badpubs [url]
# 
# Copyright 2012 California Institute of Technology. ALL RIGHTS
# RESERVED. U.S. Government Sponsorship acknowledged.

# http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=Quantitative+GSTP1+methylation+and+the+detection+of+prostate+adenocarcinoma+in+sextant+biopsies&field=title

import sys, logging, optparse, rdflib, csv, os, urllib
from lxml import etree

logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')

_optParser = optparse.OptionParser(description='Scans EDRN publications RDF for bad ones.', usage='%prog [options] [url]')
_optParser.add_option('-c', '--csv', action='store_true', dest='csv', help='Output in comma-separated value format', default=False)
_optParser.add_option('-o', '--output', dest='output', help='Output file; writes to stdout by default')
_optParser.add_option('-s', '--suggest', action='store_true', dest='suggest', help='Suggest PubMedID via database lookup')

_defaultURL      = 'http://ginger.fhcrc.org/dmcc/rdf-data/publications/rdf'
_pubMedIDPredURI = rdflib.URIRef('http://edrn.nci.nih.gov/rdf/schema.rdf#pmid')
_titlePredURI    = rdflib.URIRef('http://purl.org/dc/terms/title')
_creatorPredURI  = rdflib.URIRef('http://purl.org/dc/terms/author')
NO_TITLE         = u'«NO TITLE»'
NO_AUTHORS       = u'«NO AUTHORS»'

class Formatter(object):
    def __init__(self, output):
        self.output = output
    def format(self, subject, title, creators):
        raise NotImplementedError('Subclass "%s" failed to implement Formatter.format' % self.__class__.__name__)
    def encode(self, s):
        return s.encode('utf-8')
    def __repr__(self):
        return self.__class__.__name__


class LookupFormatter(Formatter):
    def format(self, subject, title, creators):
        params = {'db': 'pubmed', 'field': 'title', 'term': self.encode(title)}
        url = u'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?' + urllib.urlencode(params)
        xml = etree.parse(url)
        results = xml.xpath(u'/eSearchResult/IdList/Id/text()')
        suggestedID = results[0] if results else None
        self.formatWithSuggestedPubMedID(subject, title, creators, suggestedID)
    def formatWithSuggestedPubMedID(self, subject, title, creators, pubMedID):
        className = self.__class__.__name__
        raise NotImplementedError('Subclass "%s" failed to implement LookupFormatter.formatWithSuggestedPubMedID' % className)


class PlainFormatter(Formatter):
    def format(self, subject, title, creators):
        message = u'%s: %s, Creators: %s\n' % (subject, title, creators)
        self.output.write(self.encode(message))

class PlainLookupFormatter(LookupFormatter):
    def formatWithSuggestedPubMedID(self, subject, title, creators, pubMedID):
        message = u'%s: %s, Creators: %s, Suggested PubMedID: %s\n' % (
            subject, title, creators, pubMedID if pubMedID else u'«NONE»'
        )
        self.output.write(self.encode(message))
        

class CSVFormatter(Formatter):
    def __init__(self, output):
        super(CSVFormatter, self).__init__(output)
        self.writer = csv.writer(output)
    def format(self, subject, title, creators):
        subject, title, creators = self.encode(subject), self.encode(title), self.encode(creators)
        self.writer.writerow((subject, title, creators))
    

class CSVLookupFormatter(LookupFormatter):
    def __init__(self, output):
        super(CSVLookupFormatter, self).__init__(output)
        self.writer = csv.writer(output)
    def formatWithSuggestedPubMedID(self, subject, title, creators, pubMedID):
        subject, title, creators = self.encode(subject), self.encode(title), self.encode(creators)
        self.writer.writerow((subject, title, creators, pubMedID))


def parsePubs(url):
    g = rdflib.ConjunctiveGraph()
    logging.info(u'Reading from %s', url)
    g.parse(rdflib.URLInputSource(url))
    statements = {}
    count = 0
    for s, p, o in g:
        predicates = statements.get(s, {})
        statements[s] = predicates
        objects = predicates.get(p, [])
        predicates[p] = objects
        objects.append(o)
        count += 1
    logging.info(u'Total statements in %s: %d', url, count)
    return statements
    

def findMissingPubMedIDs(statements):
    logging.info(u'Checking subjects (%d in total)', len(statements))
    missing = []
    for subject, predicates in statements.iteritems():
        if _pubMedIDPredURI not in predicates:
            missing.append((subject, predicates))
    return missing
    

def outputBadPublications(missing, formatter):
    logging.info(u'Displaying bad publications using formatter %r', formatter)
    for subject, preds in missing:
        title = u'"%s"' % preds[_titlePredURI][0] if _titlePredURI in preds else NO_TITLE
        creators = u'; '.join([unicode(i) for i in preds.get(_creatorPredURI, [])]) if _creatorPredURI in preds else NO_AUTHORS
        formatter.format(subject, title, creators)
    

def checkPublications(url, formatter):
    statements = parsePubs(url)
    missing = findMissingPubMedIDs(statements)
    logging.info(u'Publications without pubmed IDs: %d', len(missing))
    missing.sort(lambda a, b: cmp(a[0], b[0]))
    outputBadPublications(missing, formatter)
    

def main(argv=None):
    if argv is None: argv = sys.argv
    options, args = _optParser.parse_args(argv)
    if len(args) > 2:
        _optParser.error('Specify URL of a publications RDF feed to check, or no URL to use the default feed')
    elif len(args) == 2:
        url = args[1]
    else:
        url = _defaultURL
    if options.output:
        output = open(options.output, 'wb')
    else:
        output = os.fdopen(sys.stdout.fileno(), 'wb')
        sys.stdout.close()
    if options.suggest:
        formatter = CSVLookupFormatter(output) if options.csv else PlainLookupFormatter(output)
    else:
        formatter = CSVFormatter(output) if options.csv else PlainFormatter(output)
    try:
        checkPublications(url, formatter)
        output.close()
    except:
        logging.exception('Failure while checking URL "%s"' % url)
        return False
    return True


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv) else -1)
    