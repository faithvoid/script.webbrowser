import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib2
import urlparse
import sys
import re
import os

# Define the addon ID and handle
addon_id = 'plugin.video.webbrowser'
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon(id=addon_id)
default_url = 'https://duckduckgo.com'

# Define paths
favourites_path = xbmc.translatePath('special://home/userdata/profiles/{}/faves.txt'.format(xbmc.getInfoLabel('System.ProfileName')))

# Define our browser history stack
history = []
forward_history = []
current_url = None

# Define the User-Agent string to mimic Mozilla Firefox
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0'

def get_html(url):
    try:
        request = urllib2.Request(url)
        request.add_header('User-Agent', USER_AGENT)
        response = urllib2.urlopen(request)
        return response.read()
    except Exception as e:
        xbmc.log('Failed to load page: %s' % e, xbmc.LOGERROR)
        return None

def strip_tags_and_extract_images_links(html, base_url):
    # Remove script and style elements
    script_re = re.compile(r'<(script|style).*?>.*?</\1>', re.DOTALL)
    html = script_re.sub('', html)
    
    # Extract image tags and replace with a placeholder
    img_re = re.compile(r'<img [^>]*src="([^"]+)"[^>]*>', re.IGNORECASE)
    images = img_re.findall(html)
    html = img_re.sub('[IMAGE]', html)
    
    # Extract anchor tags and replace with a placeholder
    a_re = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE)
    links = a_re.findall(html)
    html = a_re.sub('[LINK]', html)
    
    # Resolve image and link URLs relative to the base URL
    images = [urlparse.urljoin(base_url, img) for img in images]
    links = [(urlparse.urljoin(base_url, link[0]), link[1]) for link in links]
    
    # Remove all other tags
    tag_re = re.compile(r'<[^>]+>')
    text = tag_re.sub('', html)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    return text, images, links

def list_page(url):
    global current_url, forward_history
    html = get_html(url)
    if html is None:
        return

    current_url = url
    history.append(url)
    forward_history = []

    # Clear previous items
    xbmcplugin.setContent(addon_handle, 'files')

    # Add navigation actions
    add_navigation_items()

    # Strip HTML tags and extract images and links
    readable_text, images, links = strip_tags_and_extract_images_links(html, url)
    lines = readable_text.split('[IMAGE]')  # Split by image placeholder
    
    link_index = 0
    for i, line in enumerate(lines):
        parts = line.split('[LINK]')  # Split by link placeholder
        for j, part in enumerate(parts):
            part = part.strip()
            if part:
                list_item = xbmcgui.ListItem(label=part)
                # Add context menu item to add to favourites
                context_menu = [('Favourite', 'RunPlugin(%s?action=favourite&url=%s)' % (sys.argv[0], current_url))]
                list_item.addContextMenuItems(context_menu)
                xbmcplugin.addDirectoryItem(handle=addon_handle, url='', listitem=list_item, isFolder=False)
            
            if j < len(parts) - 1 and link_index < len(links):
                link_url, link_text = links[link_index]
                list_item = xbmcgui.ListItem(label=link_text + ' ->')
                context_menu = [('Add to Favourites', 'RunPlugin(%s?action=favourite&url=%s)' % (sys.argv[0], link_url))]
                list_item.addContextMenuItems(context_menu)
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=sys.argv[0] + '?action=navigate&url=' + link_url, listitem=list_item, isFolder=True)
                link_index += 1
        
        if i < len(images):
            image_url = images[i]
            list_item = xbmcgui.ListItem(label='Image: ' + image_url)
            list_item.setThumbnailImage(image_url)
            context_menu = [('Add to Favourites', 'RunPlugin(%s?action=favourite&url=%s)' % (sys.argv[0], image_url))]
            list_item.addContextMenuItems(context_menu)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=image_url, listitem=list_item, isFolder=False)

    xbmcplugin.endOfDirectory(addon_handle)

def goto_page():
    keyboard = xbmc.Keyboard('', 'Enter URL')
    keyboard.doModal()
    if keyboard.isConfirmed():
        url = keyboard.getText()
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url
        list_page(url)

def refresh_page():
    if current_url:
        list_page(current_url)

def back_page():
    global current_url
    if len(history) > 1:
        forward_history.append(history.pop())  # Move current page to forward history
        url = history[-1]  # Get previous page
        current_url = None  # Temporarily unset current_url to avoid adding it to history again
        list_page(url)

def forward_page():
    global current_url
    if forward_history:
        url = forward_history.pop()
        list_page(url)

def add_favourite(url):
    try:
        with open(favourites_path, 'a') as f:
            f.write(url + '\n')
        xbmc.executebuiltin("Notification(Browser, Favourite added!, 5000)")
    except Exception as e:
        xbmc.log('Failed to add favourite: %s' % e, xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(Browser, Failed to add favourite!, 5000)")

def show_favourites():
    if not os.path.exists(favourites_path):
        xbmc.executebuiltin("Notification(Browser, You have no favourites yet!, 5000)")
        return

    try:
        with open(favourites_path, 'r') as f:
            favourites = f.readlines()

        xbmcplugin.setContent(addon_handle, 'files')

        for fav in favourites:
            fav = fav.strip()
            list_item = xbmcgui.ListItem(label=fav)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=sys.argv[0] + '?action=navigate&url=' + fav, listitem=list_item, isFolder=True)

        xbmcplugin.endOfDirectory(addon_handle)
    except Exception as e:
        xbmc.log('Failed to show favourites: %s' % e, xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Error', 'Failed to load favourites.', xbmcgui.NOTIFICATION_ERROR, 5000)

def add_navigation_items():
    # Add the "Go To Page" action
    list_item = xbmcgui.ListItem(label='Go To Page')
    url = sys.argv[0] + '?action=goto'
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)

    # Add the "Refresh" action
    list_item = xbmcgui.ListItem(label='Refresh')
    url = sys.argv[0] + '?action=refresh'
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)

    # Add the "Back" action
    if len(history) > 1:
        list_item = xbmcgui.ListItem(label='Back')
        url = sys.argv[0] + '?action=back'
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)

    # Add the "Forward" action
    if forward_history:
        list_item = xbmcgui.ListItem(label='Forward')
        url = sys.argv[0] + '?action=forward'
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)

def router(paramstring):
    params = dict(urlparse.parse_qsl(paramstring))
    action = params.get('action')
    if action == 'goto':
        goto_page()
    elif action == 'refresh':
        refresh_page()
    elif action == 'back':
        back_page()
    elif action == 'forward':
        forward_page()
    elif action == 'navigate':
        url = params.get('url')
        if url:
            list_page(url)
    elif action == 'favourite':
        url = params.get('url')
        if url:
            add_favourite(url)
    elif action == 'favourites':
        show_favourites()
    else:
        list_page(default_url)

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[2] != '':
        router(sys.argv[2][1:])
    else:
        xbmcplugin.setContent(addon_handle, 'files')

        # Add the initial navigation actions
        add_navigation_items()

        # Add the "Favourites" action
        list_item = xbmcgui.ListItem(label='Favourites')
        url = sys.argv[0] + '?action=favourites'
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)

        xbmcplugin.endOfDirectory(addon_handle)
