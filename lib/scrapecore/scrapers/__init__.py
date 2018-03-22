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
from commoncore import kodi
from commoncore.threadpool import ThreadPool
from commoncore.kodi import ProgressBar
from commoncore.core import format_size, format_color
from scrapecore import scrapecore

""" Some path and general definitions """

THREAD_POOL_SIZE = 20
ADDON_ID = 'script.module.scrapecore'
sys.path.append( os.path.dirname(os.path.abspath(__file__)).replace('scrapers', ''))
CACHE_PATH = kodi.vfs.join("special://home", "userdata/addon_data/script.module.scrapecore/cache")
if not kodi.vfs.exists(CACHE_PATH): kodi.vfs.mkdir(CACHE_PATH)

enabled_scrapers = 0
result_count = 0
active_scrapers = []
supported_scrapers = []
_active_scrapers = []
search_results = []
PB = ProgressBar()

class ScraperCoreException(Exception):
	pass

""" First get a list of scraper resource modules """
kodi.set_property("new_scraper", "false", 'script.module.scrapecore')
available = scrapecore.get_installed_resources()

""" Load scrapers from each module serially """ 
for mod in available:
	path = kodi.vfs.join(mod['path'], 'scrapers')
	sys.path.append(path)
	""" Directory list the resource module """
	for filename in sorted(os.listdir(path)):
		""" Filter out some stuff """
		if not re.search('(__)|(common\.py)|(example\.py)|(all\.py)', filename) and re.search('py$', filename):
			name = filename[0:len(filename)-3]
			scraper_path = kodi.vfs.join(path, filename)
			""" Now read the scraper code and execute it """
			code = kodi.vfs.read_file(scraper_path)
			if code:
				try:
					exec code
				except ScraperCoreException as e:
					kodi.log(e)
					kodi.log("Invalid scraper: %s" % name)
					continue
				""" Scrape checks out, now access obtain an instance of the main class and store it in the list of _active_scrapers """
				classname = name+'Scraper'
				scraper = __import__('', globals(), locals(), [classname], -1)
				klass = getattr(scraper, classname)
				scraper = klass()
				""" Install the scraper if it has not already been installed """
				scrapecore.install_scraper(scraper)
				supported_scrapers.append(name)
				active_scrapers.append(scraper.service)
				_active_scrapers.append(scraper)
""" Re-write the scrapers settings xml if scraper count has changed """
if kodi.get_property("new_scraper", 'script.module.scrapecore'):
	scrapecore.write_settings_file()
	kodi.set_property("new_scraper", "false", 'script.module.scrapecore')
temp = []
_temp = []
""" Now verify each scraper is valid """
for s in supported_scrapers:
	scraper = _active_scrapers[supported_scrapers.index(s)]
	if kodi.get_setting(s +'_enable', addon_id=ADDON_ID) == 'true' and scraper.valid:
		temp.append(s)
		_temp.append(scraper)
active_scrapers = temp
_active_scrapers = _temp
del temp
del _temp

""" Some helper functions """
def get_scraper_by_name(name):
	index = active_scrapers.index(name)
	return get_scraper_by_index(index)

def get_scraper_by_index(index):
	return _active_scrapers[index]

def format_results(results):
	for r in results:
		attribs = [r['host'].upper()]
		if r['size']: attribs += [format_color(format_size(r['size']), 'blue')]
		if 'premium' in r and r['premium']: attribs += [format_color(r['premium'], 'green')]
		if r['title']: attribs += [r['title']]
		display = ' | '.join(attribs)
		results[results.index(r)]['display'] = display
	return results

"""
	The main search routine search
	Initiates a threadpool of THREAD_POOL_SIZE
	This creates a pool of worker threads with a size = the number of vaild scrapers but less then THREAD_POOL_SIZE
	
	search queues each scrapers appropriate search function into the threadpool. If the function does not exist in the scraper it continues.
	
	For most scrapers only episode_title, season, episode are needed for shows and title, year for movies.
	
	The results of each individual scraper is then fed to the process_results function to compile the list of results.
	This occurs in parallel.
	
	Duplicates are removed by raw_url and then formated by format_results

"""


def search(media, title, season=None, episode=None, year=None, episode_title=None, trakt_id=None, imdb_id=None, tmdb_id=None, tvdb_id=None, ignore_list=[], find_torrent=False):
	resolved_url = ''
	global result_count
	result_count = 0
	pool = ThreadPool(THREAD_POOL_SIZE)
	def process_results(results):
		name, verified = results
		global search_results, PB, result_count
		verified = {v['raw_url']:v for v in verified}.values()
		search_results += verified
		search_count = len(verified)
		result_count += search_count
		PB.next("Total Results: [COLOR green]%s[/COLOR]" % result_count, "Found [COLOR green]%s[/COLOR] links from [COLOR orange]%s[/COLOR]" % (search_count, name))
		
	if media == 'movie':
		args = {"title": title, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tmdb_id": tmdb_id}
		PB.new('Searching for Movie Sources', len(_active_scrapers))
		for s in _active_scrapers:
			if s.service in ignore_list: continue
			if find_torrent:
				if s.torrent:
					s.return_cached = False
				else: continue
			if 'search_movies' in dir(s): pool.queueTask(s.search_movies, args=args, taskCallback=process_results)
	else:
		args = {"title": title, "episode_title": episode_title, "season": season, "episode": episode, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tvdb_id": tvdb_id}
		PB.new('Searching for TV Sources', len(_active_scrapers))
		for s in _active_scrapers:
			if s.service in ignore_list: continue
			if find_torrent:
				if s.torrent:
					s.return_cached = False
				else: continue
			if 'search_shows' in dir(s): pool.queueTask(s.search_shows, args=args, taskCallback=process_results)
		
	pool.joinAll()
	PB.close()
	
	if len(search_results) == 0:
		kodi.notify('Search Failed', 'No results found')
		return []
	
	return format_results(search_results)

