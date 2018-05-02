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
SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
lib_path = SCRAPER_DIR.replace('scrapers', '')
sys.path.append(lib_path)
import hashlib
import json
import time
import zlib
import urllib
import random
import requests

from urlparse import urljoin, urlparse
from commoncore import kodi
from commoncore.enum import enum
from commoncore import realdebrid
from commoncore import premiumize
from commoncore import dom_parser
from commoncore.BeautifulSoup import BeautifulSoup
from commoncore.threadpool import ThreadPool
vfs = kodi.vfs
	
ADDON_ID = 'script.module.scrapecore'
CACHE_PATH = vfs.join("special://home", "userdata/addon_data/script.module.scrapecore/cache")
if not vfs.exists(CACHE_PATH): vfs.mkdir(CACHE_PATH)
VERIFY_POOLS_SIZE = 15
QUALITY = enum(LOCAL=9, HD1080=8, HD720=7, HD=6, HIGH=5, SD480=4, UNKNOWN=3, LOW=2, POOR=1)


"""
	The Base Scraper
	The essential functions provided to each scraper subtype
"""

class BaseScraper():
	session = requests.Session()
	abort_event = False
	accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
	timeout = 5
	torrent = False
	verified_results = []
	search_count = 0
	result_count = 0
	valid = True
	domains = []
	regex = {
		'hvec': re.compile('([-_\s\.]?(x265)|(hevc)[-_\s\.])', re.IGNORECASE),
		'hc': re.compile('([-_\s\.]?(HC)[-_\s\.])'),
		'hd1080': re.compile('1080p', re.IGNORECASE),
		'hd720': re.compile('720p', re.IGNORECASE),
		'sd': re.compile('480p', re.IGNORECASE),
		'low': re.compile('(320p|240p)', re.IGNORECASE),
		'mkv': re.compile('\.mkv$', re.IGNORECASE),
		'mp4': re.compile('\.(mp4|mkv)$', re.IGNORECASE),
		'avi': re.compile('\.avi$', re.IGNORECASE),
		'mpg': re.compile('\.mpg|mpeg|vob$', re.IGNORECASE),
		'flv': re.compile('\.flv$', re.IGNORECASE)
	}
	
	""" The minimal settings definition. This should be overridden if additional settings are required. """

	settings_definition = [
		'<setting label="{NAME}" type="lsep" />',
		'<setting default="true" id="{SERVICE}_enable" type="bool" label="Enable {NAME}" visible="true" />'
	]
	
	""" The minimum output is a dict of results """
	base_result = {
		"title": "", 
		"raw_url": "", 
		"service": '', 
		"host": '', 
		"size": 0, 
		"extension": '',
		"quality": QUALITY.UNKNOWN
	}
	
	def urlencode(self, params):
		return urllib.urlencode(params)
	
	def get_file_from_url(self, url):
		return os.path.basename(url)
	
	""" See regex definitions above """
	def test_quality(self, string, default=QUALITY.UNKNOWN):
		if self.regex['hd1080'].search(string): return QUALITY.HD1080
		if self.regex['hd720'].search(string): return QUALITY.HD720
		if self.regex['sd'].search(string): return QUALITY.SD480
		if self.regex['low'].search(string): return QUALITY.LOW
		return default

	def get_file_type(self, string):
		if self.regex['mkv'].search(string): return 'mkv'
		if self.regex['mp4'].search(string): return 'mp4'
		if self.regex['avi'].search(string): return 'avi'
		if self.regex['mpg'].search(string): return 'mpg'
		if self.regex['flv'].search(string): return 'flv'
		return False
	
	def is_hc(self, string):
		if self.regex['hc'].search(string): return 1
		return 0
	
	def is_hvec(self, string):
		if self.regex['hvec'].search(string): return 1
		return 0
	
	def get_domain_from_url(self, url):
		parsed_uri = urlparse( url )
		domain = '{uri.netloc}'.format(uri=parsed_uri)
		if domain.startswith('www'):
			domain=domain[4:]
		return domain
	
	def format_show_query(self, title, season, episode):
		return "%s S%02dE%02d" % (title, int(season), int(episode))
	
	def format_move_query(self, title, year):
		return "%s %s" % (title, year)
	
	def parse_dom(self, html, name=u"", attrs={}, ret=False):
		return dom_parser.parse_dom(html, name, attrs, ret)
	
	""" process_results can be overridden if a specific function should be applied to the individual result prior to being verified """
	def process_results(self, result):
		results = []
		results.append(result)
		return results
	
	""" verify_result is intended to create a media object and appended it to the list of verified media objects. 
		this can be overridden with a function to verify the link exists for example.
		verify result is executed in parallel by a ThreadPool of size VERIFY_POOLS_SIZE
		
		the processor used in verify_verify results is process_results. By default it only appends to the list of results.
	"""
	def verify_result(self, result):
		media = self.make_media_object(result[0])
		self.verified_results.append(media)
	
	def resolve_url(self, raw_url):
		return raw_url
	
	def get_domains(self):
		self.domains = []
	
	def verify_results(self, processor, results):
		self.get_domains()
		pool = ThreadPool(VERIFY_POOLS_SIZE)
		for result in results:
			if isinstance(result, list):
				for r in result:
					pool.queueTask(processor, args=r, taskCallback=self.verify_result)
			else:
				pool.queueTask(processor, args=result, taskCallback=self.verify_result)
		pool.joinAll()
		return (self.name, self.verified_results)
		
	def get_user_agent(self):
		user_agent = kodi.get_setting('user_agent')
		try: agent_refresh_time = int(kodi.get_setting('agent_refresh_time'))
		except: agent_refresh_time = 0
		if not user_agent or agent_refresh_time < (time.time() - (7 * 24 * 60 * 60)):
			user_agent = self.generate_user_agent()
			kodi.set_setting('user_agent', user_agent)
			kodi.set_setting('agent_refresh_time', str(int(time.time())))
		return user_agent
	
	def generate_user_agent(self):
		BR_VERS = [
			['%s.0' % i for i in xrange(18, 43)],
			['41.0.2228.0', '41.0.2227.1', '41.0.2227.0', '41.0.2226.0', '40.0.2214.93', '37.0.2062.124'],
			['11.0'],
			['11.0']
		]
		WIN_VERS = ['Windows NT 10.0', 'Windows NT 7.0', 'Windows NT 6.3', 'Windows NT 6.2', 'Windows NT 6.1', 'Windows NT 6.0', 'Windows NT 5.1', 'Windows NT 5.0']
		FEATURES = ['; WOW64', '; Win64; IA64', '; Win64; x64', '']
		RAND_UAS = [
			'Mozilla/5.0 ({win_ver}{feature}; rv:{br_ver}) Gecko/20100101 Firefox/{br_ver}',
			'Mozilla/5.0 ({win_ver}{feature}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{br_ver} Safari/537.36',
			'Mozilla/5.0 ({win_ver}{feature}; Trident/7.0; rv:{br_ver}) like Gecko'
		]
		index = random.randrange(len(RAND_UAS))
		user_agent = RAND_UAS[index].format(win_ver=random.choice(WIN_VERS), feature=random.choice(FEATURES), br_ver=random.choice(BR_VERS[index]))
		
		return user_agent
	
	def get_cached_response(self, url, cache_limit):
		cache_hash = hashlib.md5(str(url)).hexdigest()
		cache_file = vfs.join(CACHE_PATH, cache_hash)
		if vfs.exists(cache_file):
			temp = vfs.read_file(cache_file + '.ts')
			if (time.time() - vfs.get_stat(cache_file).st_ctime()) / 3600 > int(temp):
				vfs.rm(cache_file, quiet=True)
				vfs.rm(cache_file + '.ts', quiet=True)
				return False
			else:
				html = zlib.decompress(vfs.read_file(cache_file))
				kodi.log('Returning cached request')
				return html
		return False	
			

	def cache_response(self, url, html, cache_limit):
		if html and cache_limit:
			cache_hash = hashlib.md5(str(url)).hexdigest()
			cache_file = vfs.join(CACHE_PATH, cache_hash)
			output = html.encode('utf-8') if type(html) == unicode else html
			vfs.write_file(cache_file, zlib.compress(output))
			vfs.write_file(cache_file+'.ts', str(cache_limit))
	
	def process_response(self, response, return_type='text'):
		if return_type == 'json':
			return json.loads(response)
		elif return_type == 'xml':
			import xml.etree.ElementTree as ET
			if type(response) == unicode:
				response = response.encode("utf-8", errors="ignore")
			return ET.fromstring(response)
		elif return_type == 'soup':
			return BeautifulSoup(response)
		elif return_type == 'dom':
			return dom_parser.DomObject(response)
		else:
			return response
	
	def make_media_object(self, obj):
		media = {'title': obj['service'], "service": obj['service'], 'size': '', "host": obj['host'], "premium": ""}
		if 'title' in obj and obj['title']: media['title'] = obj['title']
		if 'url' in obj: media['url'] = obj['url']
		if 'raw_url' in obj: media['raw_url'] = obj['raw_url']
		if 'host_icon' in obj: media['host_icon'] = obj['host_icon']
		if 'size' in obj: media['size'] = obj['size']
		if 'quality' in obj: media['quality'] = obj['quality']
		else : media['quality'] = self.test_quality(media['title'])
		media['extension'] = self.get_file_type(media['title'])
		media['x265'] = self.is_hvec(media['title'])
		media['hc'] = self.is_hc(media['title'])
		media['torrent'] = False
		return media
	
	def build_url(self, uri, query, append_base):
		if query:
			uri += "?" + urllib.urlencode(query)
		if append_base:
			base_url = self.base_url
			url = urljoin(base_url, uri)
		else:
			url = uri
		return url	
	
	def request(self, uri, query=None, params=None, headers=None, timeout=None, cache_limit=0, return_type="text", append_base=True):

		if headers:
			if 'Referer' not in headers.keys(): 
				headers['Referer'] = self.referrer
			if 'Accept' not in headers.keys():	
				headers['Accept'] = self.accept
			if 'User-Agent' not in headers.keys():
				headers['User-Agent'] = self.get_user_agent()
		else:
			headers = {
			'Referer': self.referrer,
			'Accept': self.accept,
			'User-Agent': self.get_user_agent()
			}
		
		url = self.build_url(uri, query, append_base)
		if url is None: return ''

		if timeout is None:
			timeout = self.timeout	
		
		if cache_limit > 0:
			cached_response = self.get_cached_response(url, cache_limit)
			if cached_response:
				return self.process_response(cached_response, return_type)
		
		if params:
			response = self.session.post(url, data=json.dumps(params), headers=headers, timeout=timeout, verify=False)
		else:
			response = self.session.get(url, headers=headers, timeout=timeout, verify=False)	
		response.encoding = 'utf-8'
		self.last_response = response
		if response.status_code == requests.codes.ok:
			html = response.text
		elif response.status_code == 403 and '<title>Attention Required! | Cloudflare</title>' in response.text:
			kodi.log('protected by cloudflare')
			response.raise_for_status()		
		else:
			kodi.log(response)
			kodi.log(response.headers)
			response.raise_for_status()	
		
		if cache_limit > 0:
			self.cache_response(url, html, cache_limit)
			
		return self.process_response(html, return_type)
				
	def get_redirect(self, uri, append_base=True):
		headers = {
			'Referer': self.referrer,
			'Accept': self.accept,
			'User-Agent': self.get_user_agent()
		}
		if append_base:
			base_url = self.base_url
			url = urljoin(base_url, uri)
		else:
			url = uri
		response = self.session.head(url, timeout=self.timeout)
		if response.status_code == 302:
			for k in response.headers:
				if k.lower() == 'location' or k.lower() == 'content-location':
					return response.headers[k]
		else:	
			return False

	def head(self, uri, query=None, headers=None, timeout=None, append_base=True):
		if headers:
			if 'Referer' not in headers.keys(): 
				headers['Referer'] = self.referrer
			if 'Accept' not in headers.keys():	
				headers['Accept'] = self.accept
			if 'User-Agent' not in headers.keys():
				headers['User-Agent'] = self.get_user_agent()
		else:
			headers = {
			'Referer': self.referrer,
			'Accept': self.accept,
			'User-Agent': self.get_user_agent()
			}
		
		url = self.build_url(uri, query, append_base)
		if url is None: return ''

		if timeout is None:
			timeout = self.timeout
		response = self.session.head(url, headers=headers, timeout=timeout, verify=False)
		return response
		
"""
	DirectScraper
	This type inherits BaseScraper
	The simplest type of scraper
	This scraper type is intended for use where the scraper returns playable urls.
	
	resolve_url should return only the raw_url for play
"""

class DirectScraper(BaseScraper):
	def verify_result(self, result):
		media = self.make_media_object(result[0])
		self.verified_results.append(media)
	
	def resolve_url(self, raw_url):
		return raw_url	

"""
	AddonScraper
	This type inherits BaseScraper
	This scraper type is intended for use where the scraper returns plugin_urls.
	
	resolve_url should return only a properly formated plugin_url
	An example would be a youtube video to be played by the youtube addon.
	The result plugin_url would be plugin://plugin.video.youtube/?arguments
	Not yet implemented, but coming
"""

class AddonScraper(DirectScraper):
	pass
	

"""
	URLResolverScraper is fairly straight forward.
	get_hosts obtains the list of hosts from urlresolver
	
	resolve_url uses urlresolver.HostedMediaFile to resolve the raw_url if able
"""
	
class URLResolverScraper(BaseScraper):
	def get_hosts(self):
		import urlresolver
		domains = []
		for r in urlresolver.relevant_resolvers(include_universal=False):
			domains += r.domains
			domains = list(set(domains))
		return domains
	
	def verify_result(self, result):
		self.verified_results.append(result[0])
	
	def resolve_url(self, raw_url):
		import urlresolver
		try:
			source = urlresolver.HostedMediaFile(url=raw_url)
			resolved_url = source.resolve() if source else None
			return resolved_url
		except Exception, e:
			kodi.log(e)
			return ''

""" PremiumScraper
	Not yet fully completed, currently only supports RD and PM
	It will use the premium scrapers by priority to resolve the url.
	Similar to urlresolver and its universal scrapers
"""
	
class PremiumScraper(BaseScraper):
	valid = kodi.get_setting('premiumize_enable', ADDON_ID) == 'true' and kodi.get_setting('premiumize_username', ADDON_ID) != '' or kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true' and kodi.get_setting('realdebrid_token', ADDON_ID) != ''
	
	def get_domains(self):
		if kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true':
			self.realdebrid_hosts = realdebrid.get_hosts()
		else:
			self.realdebrid_hosts = []

		if kodi.get_setting('premiumize_enable', ADDON_ID) == 'true':
			self.premiumize_hosts = premiumize.get_hosts()
		else:
			self.premiumize_hosts = []
			
		self.domains = list(set(self.realdebrid_hosts + self.premiumize_hosts))
		return self.domains
	
	def verify_result(self, result):
		if result[0]['host'] not in self.domains: return
		media = self.make_media_object(result[0])
		self.verified_results.append(media)
		
	def verify_results(self, processor, results):
		self.get_domains()
		for result in results:
			if isinstance(result, list):
				for r in result:
					self.verify_result(processor(r))
			else:
				self.verify_result(processor(result))
		
		return (self.name, self.verified_results)	
	
	def resolve_url(self, raw_url):
		resolved_url = ''
		host = self.get_domain_from_url(raw_url)
		if host not in self.get_domains(): return ''
		from commoncore.dispatcher import WeightedDispatcher
		dispatcher = WeightedDispatcher()
		
		@dispatcher.register(kodi.get_setting('premiumize_priority', ADDON_ID), [raw_url])
		def pm_resolver(raw_url):
			if host not in self.premiumize_hosts: return ''
			try:
				response = premiumize.get_download(raw_url)
				return response['result']['location']
			except:
				return ''

		@dispatcher.register(kodi.get_setting('realdebrid_priority', ADDON_ID), [raw_url])
		def rd_resolver(raw_url):
			if host not in self.realdebrid_hosts: return ''
			try:
				return realdebrid.resolve_url(raw_url)
			except:
				return ''
		
		kodi.open_busy_dialog()
		try:
			resolved_url = dispatcher.run()
		except:
			kodi.close_busy_dialog()
		kodi.close_busy_dialog()
		return resolved_url

"""
	PremiumizeScraper
	This scraper will apply the PM flag to the results display
	
	resolve_url uses commoncore.premiumize.get_download to resolve the url
"""

class PremiumizeScraper(PremiumScraper):
	valid = kodi.get_setting('premiumize_enable', ADDON_ID) == 'true' and kodi.get_setting('premiumize_username', ADDON_ID) != ''
	
	def __init__(self):
		self._make_media_object = self.make_media_object
		def make_media_object(obj):
			media = self._make_media_object(obj)
			media['premium'] = 'PM'
			return media
		self.make_media_object = make_media_object
	
	def verify_result(self, result):
		if result[0]['host'] not in self.domains: return
		media = self.make_media_object(result[0])
		self.verified_results.append(media)
		
	def get_domains(self):
		self.domains = premiumize.get_hosts()
	
	def resolve_url(self, raw_url):
		response = premiumize.get_download(raw_url)
		try:
			return response['result']['location']
		except:
			return ''

"""
	RealDebridScraper
	This scraper will apply the RD flag to the results display
	
	resolve_url uses commoncore.realdebrid.resolve_url to resolve the url
"""

class RealDebridScraper(PremiumScraper):
	valid = kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true' and kodi.get_setting('realdebrid_token', ADDON_ID) != ''
	def get_domains(self):
		self.domains = realdebrid.get_hosts()
	
	def __init__(self):
		self._make_media_object = self.make_media_object
		def make_media_object(obj):
			media = self._make_media_object(obj)
			media['premium'] = 'RD'
			return media
		self.make_media_object = make_media_object
	
	def resolve_url(self, raw_url):
		resolved_url = realdebrid.resolve_url(raw_url)
		return resolved_url


"""
	TorrentScraper
	This is a special scraper type that requires a premiumize account
	raw_url can be a magnet url or a torrent url
	
	resolve url will use commoncore.premiumize.create_transfer to create a transfer to your cloud.
	it will then poll for the finished status and return the resolved_url
	the resolved url will be automatically grabbed by the commoncore.premiumize.get_folder_stream
"""
	
class TorrentScraper(BaseScraper):
	valid = (kodi.get_setting('premiumize_enable', ADDON_ID) == 'true' and kodi.get_setting('premiumize_username', ADDON_ID) != '') or kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true'
	torrent = True
	return_cached = True
		
	def get_hash_from_magnet(self, magnet):
		match = re.search("btih:([^&]+)&", magnet, re.IGNORECASE)
		if match:
			return match.group(1)
		else:
			return False
	
	def get_hash_from_url(self, url):
		match = re.search('([a-fA-F0-9]{40})', url)
		if match:
			return match.group(1)
		else:
			return False
	
	def get_hash(self, source):
		if source[0:6] == 'magnet':
			return self.get_hash_from_magnet(source)
		else:
			return self.get_hash_from_url(source)
		
	def check_hashes(self, hashes):
		results = {'realdebrid': {}, "premiumize": {}}
		if kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true':
			results['realdebrid'] = realdebrid.check_hashes(hashes)
			
		if kodi.get_setting('premiumize_enable', ADDON_ID) == 'true':
			results['premiumize'] = premiumize.check_hashes(hashes)
		return results
		
	def make_media_object(self, obj):
		media = {'title': obj['service'], "service": obj['service'], 'size': '', "host": obj['host'], "premium": ""}
		if 'title' in obj and obj['title']: media['title'] = obj['title']
		if 'url' in obj: media['url'] = obj['url']
		if 'raw_url' in obj: media['raw_url'] = obj['raw_url']
		if 'host_icon' in obj: media['host_icon'] = obj['host_icon']
		if 'size' in obj: media['size'] = obj['size']
		if 'quality' in obj: media['quality'] = obj['quality']
		else : media['quality'] = self.test_quality(media['title'])
		media['extension'] = self.get_file_type(media['title'])
		media['x265'] = self.is_hvec(media['title'])
		media['hc'] = self.is_hc(media['title'])
		media['premium'] = 'TOR'
		media['torrent'] = True
		return media
	
	def get_torrent_services(self):
		pass
	
	def verify_hash(self, hash):
		if kodi.get_setting('realdebrid_enable', ADDON_ID) == 'true':
			try:
				if self.verified_hashes['realdebrid'][hash]['rd'] != []: return True
			except: pass
		if kodi.get_setting('premiumize_enable', ADDON_ID) == 'true':
			try:
				if self.verified_hashes['premiumize']['hashes'][hash]['status'] == 'finished': return True
			except: pass
		return False
		
	def verify_results(self, processor, results):
		hashes = [self.get_hash(r['raw_url']) for r in results]
		self.verified_hashes = self.check_hashes(hashes)
		for r in results:
			hash = self.get_hash(r['raw_url'])
			if self.verify_hash(hash):
				self.verify_result([r])
		return (self.name, self.verified_results)
	
	def resolve_url(self, raw_url):
		from commoncore.dispatcher import WeightedDispatcher
		resolved_url = ''
		hash = self.get_hash(raw_url)
		kodi.set_property('Playback.Hash', hash)
		
		dispatcher = WeightedDispatcher()
		@dispatcher.register(kodi.get_setting('premiumize_priority', ADDON_ID), [raw_url])
		def premiumize_resolver(raw_url):
			resolved_url = ''
			if kodi.get_setting('premiumize_enable', ADDON_ID) != 'true': return resolved_url
			attempt = 0
			attempts = 5
			try:
				response = premiumize.create_transfer(raw_url)
				id = response['id']	
			except:
				premiumize.clear_transfers()
				response = premiumize.create_transfer(raw_url)
				id = response['id']
			try:	
				while attempt < attempts:
					folder_id = False
					file_id = False
					target_folder_id = False
					kodi.log("Resolve Attempt %s" % attempt)
					temp = premiumize.list_transfers()
					for t in temp['transfers']:
						if t['id'] == id and t['status'] == 'finished':
							if 'target_folder_id' in t: target_folder_id = t['target_folder_id']
							if 'folder_id' in t: folder_id = t['folder_id']
							if 'file_id' in t: file_id = t['file_id']
							break
					if file_id:
						response = premiumize.item_details(file_id)
						resolved_url = response['stream_link']
						return resolved_url
					if folder_id:
						response = premiumize.list_folder(folder_id)
						resolved_url = premiumize.get_folder_stream(response)
						return resolved_url
					if target_folder_id:
						response = premiumize.list_folder(target_folder_id)
						resolved_url = premiumize.get_folder_stream(response)
						return resolved_url
	
					attempt += 1
					kodi.sleep(150)
			except:
				pass
			return resolved_url
		
		@dispatcher.register(kodi.get_setting('realdebrid_priority', ADDON_ID), [raw_url])
		def realdebrid_resolver(raw_url):
			resolved_url = ''
			if kodi.get_setting('realdebrid_enable', ADDON_ID) != 'true': return resolved_url
			response = realdebrid.add_torrent(raw_url)
			try:
				torrent_id = response['id']
				info = realdebrid.get_torrent_info(torrent_id)
				file_id = realdebrid.get_stream_file(info['files'])
				if not file_id: return
				realdebrid.select_torrent_files(torrent_id, file_id)
				kodi.sleep(500)
				info = realdebrid.get_torrent_info(torrent_id)
				raw_url = info['links'][0]
				resolved_url = realdebrid.resolve_url(raw_url)
			except: pass
			return resolved_url
		
		kodi.open_busy_dialog()
		try:
			resolved_url = dispatcher.run()
		except:
			kodi.close_busy_dialog()
		kodi.close_busy_dialog()
		
		return resolved_url
