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
from lib.scrapecore import scrapecore
from commoncore.core import format_color

@kodi.register('main')
def main():
	kodi.add_menu_item({'mode': 'scraper_list'}, {'title': "Scrapers"}, icon='')
	kodi.add_menu_item({'mode': 'resource_list'}, {'title': "Installed Scraper Resources"}, icon='')
	kodi.add_menu_item({'mode': 'auth_realdebrid'}, {'title': "Authorize RealDebrid"}, icon='settings.png')
	kodi.add_menu_item({'mode': 'rebuild_settings'}, {'title': "Rebuild Settings File"}, icon='settings.png')
	kodi.add_menu_item({'mode': 'prune_cache'}, {'title': "Prune Cache"}, icon='settings.png')
	kodi.add_menu_item({'mode': 'addon_settings'}, {'title': "Settings"}, icon='settings.png')
	kodi.eod()

@kodi.register('scraper_browser')
def scraper_browser():
	if 'media' not in kodi.args:
		kodi.add_menu_item({'mode': 'scraper_browser', 'media': "shows"}, {'title': "Browse Shows"}, icon='')
		kodi.add_menu_item({'mode': 'scraper_browser', 'media': "movies"}, {'title': "Browse Movies"}, icon='')
	else:
		from lib.scrapecore import scrapers
		services = scrapers.get_browsable_scrapers(kodi.args['media'])
		for service, name in services:
			kodi.add_menu_item({'mode': 'browse_service', "service": service, "media": kodi.args['media']}, {'title': "Browse: %s" % name}, icon='browse.png')
	kodi.eod()


@kodi.register('scraper_list')
def scraper_list():
	for s in scrapecore.get_scrapers():
		if kodi.get_setting(s['service'] +'_enable') == 'true':
			title = format_color(s['name'], 'green')
		else:
			title = format_color(s['name'], 'maroon')
		menu = kodi.ContextMenu()
		menu.add('Uninstall Scraper', {"mode": "uninstall_scraper", "service": s['service'], "name": s['name']})
		kodi.add_menu_item({'mode': 'toggle_scraper', "service": s['service']}, {'title': title}, icon='', menu=menu)
	kodi.eod()

@kodi.register('uninstall_scraper')
def uninstall_scraper():
	if kodi.dialog_confirm("Click YES to proceed", "Uninstall scraper?", kodi.args['name']):
		scrapecore.delete_scraper(kodi.args['service'])
		kodi.refresh()

@kodi.register('resource_list')
def resource_list():
	for r in scrapecore.get_installed_resources():
		kodi.add_menu_item({'mode': 'void', }, {'title': r['name']}, icon='')
	kodi.eod()	

@kodi.register('rebuild_settings')
def rebuild_settings():
	scrapecore.write_settings_file()
	kodi.notify('Success', 'Settings File Written')

@kodi.register('auth_realdebrid')
def auth_realdebrid():
	from commoncore import realdebrid
	realdebrid.authorize()

@kodi.register('toggle_scraper')
def toggle_scraper():
	if kodi.get_setting(kodi.arg('service') +'_enable') == 'true':
		kodi.set_setting(kodi.arg('service') +'_enable', 'false')
	else:
		kodi.set_setting(kodi.arg('service') +'_enable', 'true')
	kodi.refresh()
	
if __name__ == '__main__': kodi.run()
