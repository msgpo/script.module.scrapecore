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
import re
from commoncore import kodi
from commoncore.baseapi import DB_CACHABLE_API, EXPIRE_TIMES
from database import DB
from commoncore.BeautifulSoup import BeautifulSoup
orig_prettify = BeautifulSoup.prettify
def prettify(encoding=None, indent_width=4):
	r = re.compile(r'^(\s*)', re.MULTILINE)
	r2 = re.compile('\s+<\/')
	r3 = re.compile("^\s+")
	temp = r.sub(r'\1' * indent_width, orig_prettify(encoding))
	output = ''	
	lines = temp.splitlines()
	for line in lines:
		index = lines.index(line)
		try:
			if r2.search(lines[index+1]):
				output += line
			else: output += r3.sub("", line) + "\n"
		except: 
			output += line
	return output

BeautifulSoup.prettify = prettify
ADDON_ID = 'script.module.scrapecore'
class API(DB_CACHABLE_API):
	base_url = ''
api = API()


def get_installed_resources():
	results = []
	temp = kodi.kodi_json_request("Addons.GetAddons", { "installed": True, 'type': 'kodi.resource.images', "properties": ["path", "name"]})
	for a in temp['result']['addons']:
		if a['type'] == 'kodi.resource.images' and a['addonid'].startswith('resource.scrapecore.'):
			del a['type']
			results.append(a)
	return results

def get_scrapers():
	return DB.query_assoc("SELECT scraper_id, name, service, enabled FROM scrapers ORDER by name DESC", force_double_array=True)

def toggle_scraper(scraper_id):
	DB.execute("UPDATE scrapers SET enabled=ABS(1-enabled) WHERE scraper_id=?", [scraper_id])
	DB.commit()

def get_enabled_scrapers():
	temp = DB.query_assoc("SELECT scraper_id, name FROM scrapers WHERE enabled=1 ORDER by name DESC", force_double_array=True)
	return [t['name'] for t in temp]

def get_scraper_info_by_name(name):
	info = DB.query_assoc("SELECT scraper_id, name, enabled FROM scrapers WHERE name=?", [name], force_double_array=False)
	if info:
		return info
	else: return False
		
def get_scraper_info_by_id(id):
	info = DB.query_assoc("SELECT scraper_id, name, enabled FROM scrapers WHERE scraper_id=?", [id], force_double_array=False)
	if info:
		return info
	else: return False

def install_scraper(scraper):
	DB.connect()
	scraper_id = DB.query("SELECT scraper_id FROM scrapers WHERE service=?", [scraper.service])
	if not scraper_id:
		kodi.set_property("new_scraper", "true", 'script.module.scrapecore')
		settings_definition = scraper.settings_definition.replace("{NAME}", scraper.name)
		settings_definition = settings_definition.replace("{SERVICE}", scraper.service)
		DB.execute("INSERT INTO scrapers(service, name, settings, enabled) VALUES(?,?,?,1)", [scraper.service, scraper.name, settings_definition])
		DB.commit()

def write_settings_file():
	settings_file = kodi.vfs.join("special://home", 'addons/%s/resources/settings.xml' % ADDON_ID)
	settings = kodi.vfs.read_file(settings_file, soup=True)
	block = settings.find('category', {"label": "Scrapers"})
	for s in block.findAll('setting'): s.decompose()
	for s in DB.query_assoc("SELECT settings FROM scrapers ORDER by name ASC", force_double_array=True):
		block.append(BeautifulSoup(s['settings']))
	kodi.vfs.write_file(settings_file, settings.prettify())

