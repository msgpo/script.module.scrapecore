# -*- coding: utf-8 -*-

'''*
	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*'''

import os
import re
import sys
import importlib
from threading import Thread, Event
from commoncore import kodi
from commoncore.threadpool import ThreadPool
from commoncore.kodi import ProgressBar
from commoncore.core import format_size, format_color, highlight
from scrapecore import scrapecore

# Some path and general definitions
THREAD_POOL_SIZE = 20
THREAD_TIMEOUT = 15
ADDON_ID = 'script.module.scrapecore'
sys.path.append( os.path.dirname(os.path.abspath(__file__)).replace('scrapers', ''))
CACHE_PATH = kodi.vfs.join("special://home", "userdata/addon_data/script.module.scrapecore/cache")
if not kodi.vfs.exists(CACHE_PATH): kodi.vfs.mkdir(CACHE_PATH)
if not kodi.vfs.exists(kodi.vfs.join("special://home", 'addons/script.module.scrapecore/resources/settings.xml')):
	scrapecore.write_settings_file()

class ScrapeCoreException(Exception):
	pass

class ScrapeCoreTimeout(Exception):
	pass

# ScrapeCore class
class ScrapeCore(object):
	PB = False
	abort_event = Event()
	results = []
	active_scrapers = {}
	count = 0
	
	def __init__(self, supported_scrapers, load_list=None, ignore_list=[]):
		# Verify each scraper is enabled removing ignored
		# We generate the list of active scrapers
		# Each scraper is given the abort event. This can be respected in the individual scraper.
		# However if ignored, the thread will be allowed to continue and its results ignored
		for s in supported_scrapers:
			s.abort_event = self.abort_event
			if s.service in ignore_list: continue
			if type(load_list) is list and s.service not in load_list: continue
			if kodi.get_setting(s.service +'_enable', addon_id=ADDON_ID) == 'true' and s.valid:
				self.active_scrapers[s.service] = s
		self.count = len(self.active_scrapers)

	def is_canceled(self):
		c = False
		try:
			c = self.PB.is_canceled()
		except:
			pass
		return c

	def handle_abort(self):
		# Wait for the format results to complete or an explicit abort event
		while True:
			if self.is_canceled() or self.abort_event.isSet():
				self.abort_event.set()
				break
			kodi.sleep(50)
	def process_results(self, results):
		if self.abort_event.is_set(): 
			self.PB.update_subheading('Aborting', 'Aborting...')
			return
		name, verified = results
		verified = {v['raw_url']:v for v in verified}.values()
		self.results += verified
		search_count = len(verified)
		self.count += search_count
		self.PB.next("Total Results: [COLOR green]%s[/COLOR]" % self.count, "Found [COLOR green]%s[/COLOR] links from [COLOR orange]%s[/COLOR]" % (search_count, name))

	def format_results(self, results):
		if self.abort_event.is_set():
			self.PB.close()
			return []
		self.PB.update_subheading('Processing Results', '')
		self.PB.update_subheading('Processing Results', 'Formating Results...')
		for r in results:
			attribs = [r['host'].upper()]
			if r['size']: r['size_sort'] = int(r['size'])
			else: r['size_sort'] = 0
			if r['size']: attribs += [format_color(format_size(r['size']), 'blue')]
			if 'premium' in r and r['premium']: attribs += [format_color(r['premium'], 'green')]
			if r['title']:
				title = r['title']
				#for h,c in [('x264', 'orange'), ('H.264', 'orange'), ('H264', 'orange'), ('x265', 'yellow')]:
				#	title = highlight(title, h, c)
				attribs += [title]
			display = ' | '.join(attribs)
			self.results[results.index(r)]['display'] = display
		kodi.sleep(250)
		self.PB.update_subheading('Processing Results', 'Removing Duplicates...')
		kodi.sleep(250)
		self.results = {v['raw_url']:v for v in results}.values()
		self.PB.update_subheading('Processing Results', 'Sorting...')
		kodi.sleep(250)
		results.sort(reverse=True, key=lambda k: (k['quality'], k['size_sort']))
		self.PB.close()
		self.abort_event.set()
		return results

	"""
	The main search routine search
	Initiates a threadpool of THREAD_POOL_SIZE with timeout THREAD_TIMEOUT
	This creates a pool of worker threads with a size = the number of vaild scrapers but less then THREAD_POOL_SIZE
	
	search queues each scrapers appropriate search function into the threadpool. If the function does not exist in the scraper it continues.
	
	For most scrapers only episode_title, season, episode are needed for shows and title, year for movies.
	
	The results of each individual scraper is then fed to the process_results function to compile the list of results.
	This occurs in parallel.
	
	Duplicates are removed by raw_url and then formated by format_results

	"""

	def search(self, media, title, season=None, episode=None, year=None, episode_title=None, trakt_id=None, imdb_id=None, tmdb_id=None, tvdb_id=None):
		self.PB = ProgressBar()
		pool = ThreadPool(THREAD_POOL_SIZE, THREAD_TIMEOUT)
		pool.__abort_event = self.abort_event
		monitor = Thread(target=self.handle_abort)
		monitor.start()
		if media == 'movie':
			self.PB.new('Searching for Movie Sources', self.count)
			args = {"title": title, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tmdb_id": tmdb_id}
			for service, scraper in self.active_scrapers.iteritems():
				if 'search_movies' in dir(scraper):
					pool.queueTask(scraper.search_movies, args=args, taskCallback=self.process_results)
		else:
			self.PB.new('Searching for Episode Sources', self.count)
			args = {"title": title, "episode_title": episode_title, "season": season, "episode": episode, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tvdb_id": tvdb_id}
			for service, scraper in self.active_scrapers.iteritems():
				if 'search_shows' in dir(scraper):
					pool.queueTask(scraper.search_shows, args=args, taskCallback=self.process_results)
				
		pool.joinAll()
		if len(self.results) == 0:
			self.PB.close()
			self.abort_event.set()
			return []
		
		return self.format_results(self.results)
	
	
supported_scrapers = []
# First get a list of scraper resource modules
kodi.set_property("new_scraper", "false", 'script.module.scrapecore')
available = scrapecore.get_installed_resources()
ignore_list = ['__init__.py', '__all__.py', 'common.py', 'example.py']
# Load scrapers from each module serially
for mod in available:
	path = kodi.vfs.join(mod['path'], 'scrapers')
	sys.path.append(path)
	# Directory list the resource module
	for filename in sorted(os.listdir(path)):
		# Ignore these
		test = filename.lower() 
		if test not in ignore_list and test.endswith('.py'):
			name = filename[0:len(filename)-3]
			scraper_path = kodi.vfs.join(path, filename)
			# Now read the scraper code and execute it
			code = kodi.vfs.read_file(scraper_path)
			if code:
				try:
					exec code
				except ScrapeCoreException as e:
					kodi.log(e)
					kodi.log("Invalid scraper: %s" % name)
					continue
				# Scrape checks out, now access obtain an instance of the main class and store it in the list of _active_scrapers
				classname = name+'Scraper'
				scraper = __import__('', globals(), locals(), [classname], -1)
				klass = getattr(scraper, classname)
				scraper = klass()
				# Install the scraper if it has not already been installed
				scrapecore.install_scraper(scraper)
				supported_scrapers.append(scraper)
# Re-write the scrapers settings xml if scraper count has changed
if kodi.get_property("new_scraper", 'script.module.scrapecore'):
	scrapecore.write_settings_file()
	kodi.set_property("new_scraper", "false", 'script.module.scrapecore')

# This is the publicly called search function
def search(media, title, season=None, episode=None, year=None, episode_title=None, trakt_id=None, imdb_id=None, tmdb_id=None, tvdb_id=None, load_list=None, ignore_list=[]):
	scrapers = ScrapeCore(supported_scrapers, load_list, ignore_list)
	return scrapers.search(media, title, season, episode, year, episode_title, trakt_id, imdb_id, tmdb_id, tvdb_id)

def get_scraper_by_name(service):
	return ScrapeCore(supported_scrapers).active_scrapers[service]
