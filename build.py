#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import string
import shutil
import datetime
import unicodedata

DATE_FORMAT = '%Y-%m-%d-%H:%M:%S'
ICAL_DATE_FORMAT = '%Y%m%dT%H%M%SZ'
ATOM_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


# Helpers


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError:
        pass


# Copy a folder into the build directory.
def add_to_build(main_folder, folder):
    build_folder = os.path.join(main_folder, 'build')
    mkdir_p(build_folder)

    src = os.path.join(main_folder, folder)
    dest = os.path.join(build_folder, folder)
    shutil.copytree(src, dest)


# Shortcut for python file creation.
def write_file(folder, file_name, content):
    mkdir_p(folder)
    file = open(os.path.join(folder, file_name), 'w')
    file.write('\n'.join(content))
    file.close()


# Shortcut for python file reading.
def read_file(folder, file_name):
    file_descriptor = open(os.path.join(folder, file_name))
    content = file_descriptor.read()
    file_descriptor.close()
    return content


# File data extraction


# Transform event file into a dictionary.
def get_event_from_file(folder, file):
    content = open(os.path.join(folder, file)).read()
    lines = content.split('\n')
    event = {}

    for line in lines:
        parsing = line.split(':')
        key = parsing.pop(0)
        value = ':'.join(parsing)[1:]
        event[key] = value
    event['file_name'] = file[:-4]

    return event


# Transform event files into a dictionnary that match a country name with a
# list event dictionnary.
def get_events_from_folder(main_folder):
    events = {}
    archives = {}
    event_folder = os.path.join(main_folder, 'events')
    date = datetime.datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0)

    for (folder, folders, files) in os.walk(event_folder):

        if folder is not event_folder:
            country = os.path.basename(folder)
            if country not in events:
                events[country] = []
                archives[country] = []

            for file in filter(lambda file: file[-4:] == '.yml', files):
                event = get_event_from_file(folder, file)
                event['country'] = country
                end = datetime.datetime.strptime(event['end'], DATE_FORMAT)

                if (end > date):
                    events[country].append(event)
                else:
                    archives[country].append(event)

            events[country] = sorted(
                events[country],
                key=lambda event: event['start'],
                reverse=True
            )

    return (events, archives)


# HTML rendering

def build_header(partial_folder):
    return open(os.path.join(partial_folder, 'header.html')).read()


def build_footer(partial_folder):
    return open(os.path.join(partial_folder, 'footer.html')).read()


event_template = """<div class="w150p">
<div class="main-date">
    <p class="day">$startday</p>
    <p class="dayn">$startdayn</p>
    <p class="month">$startmonth</p>
    <p class="year">$startyear</p>
</div>
</div>
<div class="flex-item-fluid">
<h3><a href="$permalink">$name</a></h3>
<p class="date">From $start_render to $end_render</p>
<p class="address">$place<br />$address_render</p>
<p class=links>
<a href="$link">URL</a> -
<a href="$ical_url">ICAL</a> -
<a href="http://www.openstreetmap.org/search?query=$address">MAP</a>"""


def prepare_event(event):
    start = datetime.datetime.strptime(event['start'], DATE_FORMAT)
    end = datetime.datetime.strptime(event['end'], DATE_FORMAT)
    permalink = os.path.join(
        'events',
        get_html_event_folder(event['country'], event),
        get_html_event_file_name(event)
    )

    event.update({
        'short_start': event["start"][:10],
        'startday': start.strftime("%A"),
        'startdayn': start.strftime("%d"),
        'startmonth': start.strftime("%b"),
        'startyear': start.strftime("%Y"),
        'address_render': event['address'].replace(' - ', '<br />'),
        'start_render': start.strftime("%A %d %B %H:%M"),
        'end_render': end.strftime("%A %d %B %H:%M"),
        'ical_url': 'ical/%s/%s.ical' % (event['country'], event['file_name']),
        'permalink': permalink
    })
    return event


def get_html_event(event):
    content = []
    event = prepare_event(event)
    content.append('<div class="event flex-container">')
    content.append(string.Template(event_template).substitute(event))
    if 'cfp' in event:
        content.append('<a href="%s"> - CFP</a>' % event['cfp'])
    content.append('</p></div></div>')

    return '\n'.join(content)


country_header_template = """<div class="country-section">
<div class="country-title">
<h2 class="country" id="$country">$country_capitalize</h2>
<a href="ical/$country/$country.ical" class="ical">ICAL</a>
</div>
"""


def build_event_list(events):
    content = []
    countries = list(events.keys())
    countries.sort()

    content.append('<div class="events">')

    content.append('<header>')
    for country in countries:
        country_tuple = (country, country.capitalize())
        content.append('<a href="#%s">%s</a>' % country_tuple)

    content.append('</header>')
    for country in countries:

        if len(events[country]) > 0:
            template = string.Template(country_header_template)
            content.append(template.substitute({
                'country': country,
                'country_capitalize': country.capitalize(),
            }))

            for event in reversed(events[country]):
                content.append(get_html_event(event))

            content.append('</div>')

    return '\n'.join(content)


def build_index_page(main_folder, events):
    content = []
    partial_folder = os.path.join(main_folder, 'partials')
    build_folder = os.path.join(main_folder, 'build')

    content.append(build_header(partial_folder))
    content.append(build_event_list(events))
    content.append(build_footer(partial_folder))

    mkdir_p(build_folder)
    write_file(build_folder, 'index.html', content)


# Single event HTML rendering


def build_event_pages(main_folder, events):
    partial_folder = os.path.join(main_folder, 'partials')
    template_folder = os.path.join(main_folder, 'templates')
    build_folder = os.path.join(main_folder, 'build', 'events')

    single_event_template = make_event_template(
        partial_folder,
        template_folder
    )

    for country in events.keys():
        country_folder = os.path.join(build_folder, country)
        build_country_events_page(
            country_folder,
            events[country],
            single_event_template
        )


def make_event_template(partial_folder, template_folder):
    return "\n".join([
        read_file(partial_folder, 'header_event.html'),
        read_file(template_folder, 'event.html'),
        read_file(partial_folder, 'footer.html')
    ])


def build_country_events_page(country_folder, events, single_event_template):
    for event in events:
        build_event_page(country_folder, event, single_event_template)


def build_event_page(country_folder, event, single_event_template):
    folder = make_html_event_folder(country_folder, event)
    file_name = get_html_event_file_name(event)
    template = string.Template(single_event_template)
    event = prepare_event(event)
    html_content = template.substitute(event)
    write_file(folder, file_name, [html_content])


def make_html_event_folder(country_folder, event):
    folder = get_html_event_folder(country_folder, event)
    mkdir_p(folder)
    return folder


def get_html_event_folder(country_folder, event):
    start = event['start'][:10].replace('-', '/')
    return os.path.join(country_folder, start)


def get_html_event_file_name(event):
    event_name = event['name']
    if hasattr(event_name, 'decode'):
        event_name = event_name.decode('utf-8')
    file_name = unicodedata.normalize('NFKD', event_name) \
                           .encode('ascii', 'ignore')
    if type(file_name) == bytes and type(file_name) != str:
        file_name = file_name.decode('utf-8')
    file_name = file_name.lower()
    file_name = re.sub(r'[^a-z0-9]+', '-', file_name).strip('-')
    file_name = re.sub(r'[-]+', '-', file_name)

    return '%s.html' % file_name


# Ical rendering

ical_header_template = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//HackerEvents//NONSGML HackerMeetups Calendar//EN
X-WR-CALNAME:Hacker Events in $country"""

ical_template = """BEGIN:VEVENT
UID: $uid
DTSTAMP:$current
DTSTART:$start_ical
DTEND: $end_ical
LOCATION: $place - $address
SUMMARY:$name
URL:$link
END:VEVENT"""

ical_footer_template = """END:VCALENDAR"""


def get_ical_header(country):
    template = string.Template(ical_header_template)
    return template.substitute({'country': country})


def get_ical_footer():
    return ical_footer_template


# Turn an event into its iCal representation.
def get_ical_event(event, now):
    start = datetime.datetime.strptime(event['start'], DATE_FORMAT)
    end = datetime.datetime.strptime(event['end'], DATE_FORMAT)
    event['start_ical'] = start.strftime(ICAL_DATE_FORMAT)
    event['end_ical'] = end.strftime(ICAL_DATE_FORMAT)
    event['current'] = now.strftime(ICAL_DATE_FORMAT)
    event['uid'] = event['file_name']
    return string.Template(ical_template).substitute(event)


# Generate an ical for each event and for each country.
def build_ical_files(main_folder, events):
    now = datetime.datetime.now()
    countries = events.keys()
    build_folder = os.path.join(main_folder, 'build')
    mkdir_p(build_folder)

    for country in countries:

        all_content = []
        all_content.append(get_ical_header(country))

        country_folder = os.path.join(build_folder, 'ical', country)
        mkdir_p(country_folder)

        for event in reversed(events[country]):
            ical_event = get_ical_event(event, now)

            content = []
            content.append(get_ical_header(country))
            content.append(ical_event)
            content.append(get_ical_footer())

            all_content.append(ical_event)

            write_file(country_folder, "%s.ical" % event['file_name'], content)

        all_content.append(get_ical_footer())
        write_file(country_folder, "%s.ical" % country.lower(), all_content)

# Atom rendering

atom_header_template = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>$title</title>
  <link
    href="$feed_url"
    rel="self" type="application/atom+xml"
  />
  <link
    href="$site_url"
    rel="alternate" type="application/xhtml+xml"
  />
  <id>$atom_id</id>
  <updated>$updated</updated>
  <author>
    <name>Hacker Events</name>
  </author>
"""

atom_entry_template = """
  <entry>
    <title>$name</title>
    <id>$atom_id</id>
    <published>$atom_published</published>
    <updated>$atom_updated</updated>
    <link href="$link"/>
    <summary>
        on $start_render @ $place ($atom_country) $atom_tags
    </summary>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml">
        <h2>From $start_render to $end_render</h2>
        <p>$place<br />$address_render<br />$atom_country</p>
        <p>
          <a href="$link">URL</a> -
          <a href="$ical_url">ICAL</a> -
          <a href="http://www.openstreetmap.org/search?query=$address">MAP</a>
        </p>
      </div>
    </content>
  </entry>
"""

atom_footer = "</feed>"


def get_atom_id(date, fragment):
    domain = 'hackerevents.org'
    date = date.strftime('%Y-%m-%d')
    return "tag:%s,%s:%s" % (domain, date, fragment)


def get_atom_header():
    template = string.Template(atom_header_template)
    date = datetime.datetime.utcnow()
    updated = date.strftime(ATOM_DATE_FORMAT)
    return template.substitute({
        'title': 'Hacker Events',
        'feed_url': 'https://www.hackerevents.org/feed.atom',
        'site_url': 'https://www.hackerevents.org',
        'atom_id': get_atom_id(date, 'atomfeed'),
        'updated': updated,
    })


def get_atom_entry(event):
    start = datetime.datetime.strptime(event['start'], DATE_FORMAT)
    added = datetime.datetime.strptime(event['added'], DATE_FORMAT)
    fragment = '-'.join(event['uid'].split('-')[1:])
    event.update({
        'atom_id': get_atom_id(start, fragment),
        'atom_published': added.strftime(ATOM_DATE_FORMAT),
        'atom_updated': added.strftime(ATOM_DATE_FORMAT),
        'atom_tags': event.get('tags', ''),
        'atom_country': event.get('country', '').capitalize()
    })
    return string.Template(atom_entry_template).substitute(event)


def get_atom_body(events):
    atom_events = [x for l in events.values() for x in l]
    atom_events.sort(key=lambda x: x['added'], reverse=True)
    content = [get_atom_entry(x) for x in atom_events]
    return '\n'.join(content)


def build_atom_feed(main_folder, events):
    content = []
    build_folder = os.path.join(main_folder, 'build')

    content.append(get_atom_header())
    content.append(get_atom_body(events))
    content.append(atom_footer)

    mkdir_p(build_folder)
    write_file(build_folder, 'feed.atom', content)

# Archives page

archive_title = "<h1>Archives</h1>"
archive_line_template = """
<li><a href="$permalink">$short_start: $name at $place ($country)</a></p>
"""


def build_archive_page(main_folder, events):
    content = []
    build_folder = os.path.join(main_folder, 'build')

    content.append(get_html_header(main_folder))
    content.append(archive_title)
    content += build_archive_list(events)
    content.append(get_html_footer(main_folder))

    mkdir_p(build_folder)
    write_file(build_folder, 'archives.html', content)


def get_html_header(main_folder):
    partial_folder = os.path.join(main_folder, 'partials')
    return read_file(partial_folder, 'header.html')


def get_html_footer(main_folder):
    partial_folder = os.path.join(main_folder, 'partials')
    return read_file(partial_folder, 'footer.html')


def build_archive_list(events):
    content = ["<ul>"]
    archive_line = string.Template(archive_line_template)

    for event in prepare_archive_list(events):
        event = prepare_event(event)
        content.append(archive_line.substitute(event))

    content.append("</ul>")

    return content


def prepare_archive_list(events):
    event_list = []
    for country in events:
        event_list += events[country]

    return sorted(
        event_list,
        key=lambda event: event["start"],
        reverse=True
    )


# Main script

if __name__ == '__main__':

    main_folder = os.path.dirname(os.path.abspath(__file__))
    build_folder = os.path.join(main_folder, 'build')

    try:
        shutil.rmtree(build_folder)
    except:
        pass

    print("Start build...")

    (events, archives) = get_events_from_folder(main_folder)
    build_index_page(main_folder, events)
    build_event_pages(main_folder, events)
    build_event_pages(main_folder, archives)
    build_archive_page(main_folder, archives)
    build_ical_files(main_folder, events)
    build_atom_feed(main_folder, events)

    add_to_build(main_folder, 'styles')
    add_to_build(main_folder, 'assets')

    print("Build finished.")
