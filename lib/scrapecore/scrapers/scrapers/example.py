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

from commoncore import kodi
from commoncore.baseapi import EXPIRE_TIMES
from scrapecore.scrapers.common import DirectScraper, QUALITY

"""
	Example standard scraper based on Direct Scraper class inherited from scrapecore.scrapers.common.DirectScraper
	There are several Base Scraper types: DirectScraper, URLResolverScraper, PremiumScraper, PremiumizeScraper, RealDebridScraper, TorrentScraper
	The base difference is in the definition of the resolve_url method.

	Basic required definitions:
		service: this is the shorthand definition of the scraper. it must be unique and should follow the definition requirements for a python class		
		filename: for the service `example`, the filename must be example.py containg the class `exampleScraper`
		name: A free text description for the service. It is used for display purposes. This does not need to be unique.
		base_url: used by build_url method called by request, see below
		referrer: likely this is the same as base_url, unless required
		settings_definition: custom settings can be entered into the scrapecore settings.xml file. {NAME}, {SERVICE} and {VERSION} are substituted later.

	Basic methods:
		search_shows: called by the main search routine. It is skipped if not defined in the scraper
		search_movies
		resolve_url: Optional to override the default function defined in the base scraper. See scrapecore.scrapers.common for examples.

"""


class exampleScraper(DirectScraper):
	service='example'
	name='Sweet example scraper'
	base_url = 'http://www.exampletv.com'
	referrer = 'http://www.exampletv.com'
	
	settings_definition = ['<setting label="{NAME}" type="lsep" />',
		'<setting default="false" id="{SERVICE}_enable" type="bool" label="Enable {NAME}" visible="true" />'
	]
	
	def search_shows(self, args):
		results = []
		"""
			args is supplied by scrapers.search with the following keys
			for shows args = {"title": title, "episode_title": episode_title, "season": season, "episode": episode, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tvdb_id": tvdb_id}
			for movies args = {"title": title, "year": year, "trakt_id": trakt_id, "imdb_id": imdb_id, "tmdb_id": tmdb_id}

			The output of the search function should pass list of media objects.
			The core of is the request method.
			Sessions are utilized so that cookies are automatically used for serial requests.
			request(uri, query=None, params=None, headers=None, timeout=None, cache_limit=0, return_type="text", append_base=True, get_redirect=False)
			Example:
				xml = self.request('/videos/show', query={"title": "Great show"}, return_type="xml")
				This will call `http://www.exampletv.com/videos/show?title=Great+show`
				returning a xml.etree.ElementTree object
				See scrapecore.scrapers.common for further details
				A dictionary params will create a post request
				
				cache_limit > 0 will cache the response to disk for a number of hours. There are defined times in commoncore.baseapi
				EXPIRE_TIMES = enum(FLUSH=-2, NEVER=-1, FIFTEENMIN=.25, THIRTYMIN=.5, HOUR=1, FOURHOURS=4, EIGHTHOURS=8, TWELVEHOURS=12, DAY=24, THREEDAYS=72, WEEK=168)
				FLUSH will erase the cached response
				NEVER will never expire once cached
				Units are hours
				
			base_result = {
			"title":		"", 
			"raw_url":		"", 
			"service":		self.service, 
			"host":			'', 	# exampletv.com
			"size":			0, 		500000
			"extension":	'',
			"quality": 		QUALITY.UNKNOWN
			}
			
			The quality definitions are used for sorting as well as icon determination:
			QUALITY = enum(LOCAL=9, HD1080=8, HD720=7, HD=6, HIGH=5, SD480=4, UNKNOWN=3, LOW=2, POOR=1)
			
			There are several helper functions for extracting quality, HVEC, extension from the title or other strings.
			See scrapecore.scrapers.common for examples
			Example quality = self.test_quality(title)
			
			The verify_results method supplies the list of results to the ThreadPool that compiles the results
			Dulicates are filtered out at the end based on raw_url
		
		"""
		
		results = self.verify_results(self.process_results, results)
		return results
	
	def resolve_url(self, raw_url):
		resolved_url = raw_url

		"""
		Do final resolve work here.
		See scrapecore.scrapers.common for examples for Torrent and URLResolver
		"""

		return resolved_url
