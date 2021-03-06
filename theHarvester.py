#!/usr/bin/env python
import argparse
import google  # https://pypi.python.org/pypi/google
import Queue
import re
import socket
import sys
import threading
import time
import urllib2

import googlesearch


class Worker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            # Grab IP off the queue
            url = th.queue.get()
            try:
                print "[+] Scraping any emails from: " + url
                request = urllib2.Request(url)
                response = urllib2.urlopen(request).read()
                for badchar in ('>', ':', '=', '<', '/', '\\', ';', '&', '%3A', '%3D', '%3C'):
                    response = response.replace(badchar, ' ')
                emails = re.findall(r"[a-zA-Z0-9.-_]*@(?:[a-z0-9.-]*\.)?" + th.domain, response, re.I)
                if emails:
                    for e in emails:
                        th.allEmails.append(e)
            except:
                print "[-] Timed out after " + str(th.url_timeout) + " seconds...can't reach url: " + url

            th.queue.task_done()


class TheHarvester:

    def __init__(self, active, data_source, domain, search_max, save_emails, delay, url_timeout, num_threads):
        self.active = active
        self.data_source = data_source.lower()
        self.domain = domain

        self.search_max = search_max
        if self.search_max < 100:
            self.numMax = self.search_max
        else:
            self.numMax = 100

        self.save_emails = save_emails
        self.delay = delay
        self.url_timeout = url_timeout
        self.allEmails = []

        socket.setdefaulttimeout(self.url_timeout)

        # Create queue and specify the number of worker threads.
        self.queue = Queue.Queue()
        self.num_threads = num_threads

    def go(self):
        # Kickoff the threadpool.
        for i in range(self.num_threads):
            thread = Worker()
            thread.daemon = True
            thread.start()

        if self.data_source == "all":
            self.google_search()
            self.pgp_search()
        elif self.data_source == "google":
            self.google_search()
        elif self.data_source == "pgp":
            self.pgp_search()
        else:
            print "[-] Unknown data source type"
            sys.exit()

        # Display emails
        self.display_emails()

        # Save emails to file
        if self.save_emails and self.allEmails:
            fh = open(self.domain + '_' + get_timestamp() + '.txt', 'a')
            for email in self.parsedEmails:
                fh.write(email + "\n")
            fh.close()

    def google_search(self):
        # Retrieve pages based on domain search query
        #print "[*] Searching for email addresses in " + str(self.search_max) + " sites and waiting " + str(self.delay) + " seconds between searches"

        # Search for emails based on the search string "@<DOMAIN>"
        print "[*] (PASSIVE) Searching for emails in Google search results: @\"" + self.domain + "\""
        google_results = googlesearch.SearchGoogle(self.domain, self.search_max, self.delay)
        emails = google_results.process()
        if emails:
            for e in emails:
                self.allEmails.append(e)

        # Search for emails not within the domain's site (-site:<domain>)
        query = self.domain + " -site:" + self.domain
        print "[*] (PASSIVE) Searching for emails NOT within the domain's site: " + query
        for url in google.search(query, start=0, stop=self.search_max, num=self.numMax, pause=self.delay, extra_params={'filter': '0'}):
            self.queue.put(url)

        # Search for emails within the domain's site (site:<domain>)
        if self.active:
            query = "site:" + self.domain
            print "[*] (ACTIVE) Searching for emails within the domain's sites: " + self.domain
            for url in google.search(query, start=0, stop=self.search_max, num=self.numMax, pause=self.delay, extra_params={'filter': '0'}):
                self.queue.put(url)
        else:
            print "[*] Active seach (-a) not specified, skipping searching for emails within the domain's sites (*." + self.domain + ")"

        th.queue.join()

    '''def pgp_search(self):
        url = "https://pgp.mit.edu/pks/lookup?search=" + self.domain + "&op=index"
        self.find_emails(url)'''

    def display_emails(self):
        if not self.allEmails:
            print "[-] No emails found"
        else:
            self.parsedEmails = list(sorted(set([element.lower() for element in self.allEmails])))
            print "\n[+] " + str(len(self.parsedEmails)) + " unique emails found:"
            print "---------------------------"
            for email in self.parsedEmails:
                print email


def get_timestamp():
    now = time.localtime()
    timestamp = time.strftime('%Y%m%d_%H%M%S', now)
    return timestamp

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='theHarvester2')
    data_sources = ['all', 'google']  # , 'pgp']
    parser.add_argument('-a', dest='active', action='store_true', default=False, help='Conduct an active search.  This could potentially scrape target domain and sub-domains from your IP (default is false)')
    parser.add_argument('-b', dest='data_source', action='store', required=True, help='Specify data source (' + ', '.join(data_sources) + ')')
    parser.add_argument('-d', dest='domain', action='store', required=True, help='Domain to search')
    parser.add_argument('-l', dest='search_max', action='store', type=int, default=100, help='Maximum results to search (default and minimum is 100)')
    parser.add_argument('-f', dest='save_emails', action='store_true', default=False, help='Save the emails to emails_<TIMESTAMP>.txt file')
    parser.add_argument('-e', dest='delay', action='store', type=float, default=7.0, help='Delay (in seconds) between searches.  If it\'s too small Google may block your IP, too big and your search may take a while (default 7).')
    parser.add_argument('-t', dest='url_timeout', action='store', type=int, default=5, help='Number of seconds to wait before timeout for unreachable/stale pages (default 5)')
    parser.add_argument('-n', dest='num_threads', action='store', type=int, default=8, help='Number of search threads (default is 8)')

    args = parser.parse_args()

    if args.data_source.lower() not in data_sources:
        print "[-] Invalid search engine...specify (" + ', '.join(data_sources) + ")"
        sys.exit()
    if args.delay < 0:
        print "[!] Delay (-e) must be greater than 0"
        sys.exit()
    if args.url_timeout < 0:
        print "[!] URL timeout (-t) must be greater than 0"
        sys.exit()
    if args.num_threads < 0:
        print "[!] Number of threads (-n) must be greater than 0"
        sys.exit()

    #print vars(args)
    th = TheHarvester(**vars(args))
    th.go()

    print "\n[+] Done!"
