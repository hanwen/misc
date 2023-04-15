#!/usr/bin/python
# SPDX-FileCopyrightText: 2015-2023 Han-Wen Nienhuys <hanwenn@gmail.com>
# SPDX-License-Identifier: Apache-2.0

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
import getopt
import re
import string
import tempfile
import shutil
import glob

verbose_p = 0
keep_temp_dir_p = 0
temp_dir = ''
debug_p = 0
def setup_temp ():
	''' Create a temporary directory, and return its name. '''
	if not __main__.keep_temp_dir_p:
		__main__.temp_dir = tempfile.mktemp (__main__.program_name)
	try:
		os.mkdir (__main__.temp_dir, 0o0777)
	except OSError:
		pass

	return __main__.temp_dir


def popen (cmd):
	sys.stderr.write ('Invoking `%s\'\n' % cmd)
	return os.popen (cmd)

def tex_find_file (f):
	s = popen ('kpsewhich \"%s\"' %f).read()
	if s :
		return s[:-1]
	else:
		raise "Not found"
	
def system (cmd):
	sys.stderr.write ('Invoking `%s\'\n' % cmd)
	st = os.system (cmd)
	if st:
		sys.stderr.write ('Command failed\n')
		raise "Command failed"

	return 0

def help ():
	sys.stdout.write (r"""
DESCRIPTION

  install-type1.py -- install Type1 fonts into LaTeX tree.

This script will run the standard procedure for incorporating a Type1 font
into a texmf tree.

USAGE

  install-type1.py [OPTIONS] PATTERN

will process all files matching PATTERN*.pfb

OPTIONS:

 --help
 --texmf-dir=DIR     specify base directory for files
 --namemap=MAP       add another map file linking PFB and TeX file names,
                     and full font names
 --basepfb-dir=DIR   where to find the PFB and AFM files.
 --dvipsmap          write map files for dvips
 --debug             do not remove temporary directory

EXAMPLE:

  install-type1.py --dvipsmap \
     --texmf-dir /tmp/texmf --basepfb-dir /tmp/adobe/ ag

this will install all Adobe AvantGarde fonts (ag*pfb) into a texmf
tree located at /tmp/texmf.  A map file will be written to
imported-fonts.map (under texmf/dvips/config).

The font files are assumed to reside under a directory relative to CWD
or --basepfb-dir, which describes their name, eg. AvantGarde/ag*.pfb

When you TEXMF as follows, all tools should continue to work.

  {/tmp/texmf//,{!!/usr/share/texmf,!!/usr/local/share/texmf}}


BUGS:

Make sure that file names do not contain any spaces

""")


(options, files)  = getopt.getopt (sys.argv[1:],
				   '', ['texmf-dir=',
					'namemap=',
					'help',
					'debug',
					'basepfb-dir=',
					'dvipsmap'
					])
namemaps = ['adobe.map']
texmf_dir = 'texmf'
base_pfb_dir = './'
write_dvips_map_p = 0

for (o,a) in options:
	if 0:
		pass
	elif o == '--help':
		help ()
		sys.exit (0)
		
	elif o == '--texmf-dir':
		texmf_dir = a
	elif o == '--namemap':
		namemaps.append( a)
	elif o == '--basepfb-dir':
		base_pfb_dir = a
	elif o == '--dvipsmap':
		write_dvips_map_p = 1
	elif o == '--debug':
		debug_p = 1

namemaps = map (tex_find_file, namemaps)

if base_pfb_dir[-1] != '/':
	base_pfb_dir += '/'



dvipsmap = ''
berry_names = {}
fontinst_file = tex_find_file ('fontinst.sty')

font_dir = os.path.join (texmf_dir, 'fonts')
psnfs_dir = os.path.join (texmf_dir, 'tex/latex/psnfss/')
dvips_dir = os.path.join (texmf_dir, 'dvips/config/')


# after joining! 
base_pfb_dir = os.path.abspath (base_pfb_dir)
texmf_dir = os.path.abspath (texmf_dir)



def read_name_map (mapfile):
	dict = {}
	
	ls = open(mapfile).readlines()
	for l in ls:
		if re.search ("^@c", l):
			continue

		l = l[:-1]

		fields = string.split (l)

		if len (fields) < 5:
			continue

		berry = fields[0]
		full = fields[1]
		ps_filename = fields[4]
		dict[ps_filename] = (berry, full)
	
	
	return dict


def dvips_map_string (psnamemap):
	dvipsmap = ''
	for (k,v) in psnamemap.items():
		(b,f) = v

		recode = "\"TeXBase1Encoding ReEncodeFont\""
		dvipsmap += '%s \t\t %s %s <8r.enc <%s.pfb\n' % (
			re.sub ('8a', '8r', b), f, recode, b)

	return dvipsmap


def write_psfonts_map (maps):
	str = dvips_map_string (maps)
	open (os.path.join (dvips_dir, 'imported-psfonts.map'),'w').write (str)
	new_map = os.path.join (dvips_dir, 'psfonts.map')

	# prevent circularity when reading old psfonts.map
	if os.path.exists (new_map):
		os.unlink (new_map)
		
	global_fm = tex_find_file('psfonts.map')
	open (new_map,'w').write (open (global_fm).read () + str)

def mkdir_if_not_exist (a):
	if not os.path.isdir (a):
		system ("mkdir -p %s" % a)

def move_to_dir (src, dest):
	mkdir_if_not_exist (dest) 
	shutil.copy2 (src,dest)
	os.unlink (src)
	

def convert_one_family (family, pfb_files, ps_to_berry_mapping):
	tempdir = tempfile.mktemp ('install-type1')
	if debug_p:
		tempdir = '/tmp/install-type1.dir'
		sys.stderr.write ('Temp dir is %s\n' % tempdir)
		mkdir_if_not_exist (tempdir)
		os.system ('rm -f %s/*' % tempdir)
	else:
		os.mkdir (tempdir, 0o0700)

	curdir = os.getcwd()
	os.chdir (tempdir)

	(dir, base) = os.path.split (pfb_files[0])
	font_name_dir = re.sub (base_pfb_dir + '/', '', dir)
	
	base =  os.path.splitext (base)[0]
	for p in pfb_files:
		(dir, base) = os.path.split (p)
		base = os.path.splitext (base)[0]
		
		(berry, full) = ps_to_berry_mapping [base]

		## ugr.
		##
#		shutil.copy2 (p, './')
#		shutil.copy2 (re.sub ('.pfb','.afm',p), './' )
		shutil.copy2 (p, './%s.pfb' % berry)
		shutil.copy2 (re.sub ('.pfb','.afm',p), './%s.afm' % berry)

	open ('foo.tex', 'w').write ( r'\input %s \latinfamily{%s}{}\bye' %
				      (fontinst_file, family))

	system ('latex foo')
	
	for f in glob.glob ('*.pl'):
		system ('pltotf %s' % f)

	for f in glob.glob ('*.vpl'):
		system ('vptovf %s' % f)

	system ('chmod u+w *')
	for ext in ['vf', 'afm', 'tfm', 'fd', 'pfb']:
		subdir = ext
		if subdir== 'pfb':
			subdir = 'type1' ## urg.
		dest = os.path.join (font_dir, '%s/%s' % (subdir, font_name_dir))
		if ext == 'fd':
			dest = psnfs_dir
			
		for f in glob.glob ('*.%s' % ext):
			move_to_dir (f, dest)
	if not debug_p:
		shutil.rmtree (tempdir)
	os.chdir (curdir)


if not files:
	sys.stderr.write ("No fonts specified, try --help.\n")
	sys.exit (2)


psnamemap = {}

for a in [texmf_dir, font_dir, psnfs_dir, dvips_dir]:
	mkdir_if_not_exist (a)

for m in namemaps:
	psnamemap.update (read_name_map (m))

if  write_dvips_map_p:
	write_psfonts_map (psnamemap)

todo =[]
for f in files:
	ls = popen ('find %s -name \'%s*pfb\'' % (base_pfb_dir, f)).readlines ()
	for l in ls:
		l = l[:-1]
		todo .append (l)

sys.stdout.write ('Installing:')

font_sets = {}
for t in todo:
	base = os.path.splitext (os.path.basename (t))[0]
	
	(berry, full) = psnamemap [base]
	family = berry[0:3]
	if not font_sets.has_key (family):
		font_sets[family] = []

	font_sets[family].append (t)


for (fam, pfbs) in font_sets.items():
	bases = map (os.path.basename, pfbs)

	sys.stdout.write ('Family %s (%s)\n' % (fam, string.join (bases)))
	convert_one_family (fam, pfbs, psnamemap)
