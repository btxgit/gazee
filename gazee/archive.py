#!/usr/bin/env python
"""
These functions were designed to work on archives without writing anything to disk
before it's necessary.  Thus, no extracting all files to a temp directory.  Should
significantly speed up anything aside from a solid RAR archive.
"""

__author__ = "btx"
__package__ = "gazee.archive"

import os
import sys
import logging
import zipfile
import rarfile
import traceback
from io import BytesIO
from PIL import Image
import subprocess
import math

log = logging.getLogger(__name__)


def identify_arch(cp):
    """ Returns 1 for a zipfile, 2 for a rarfile, and None for anything else """

    sig = None

    with open(cp, 'rb') as fd:
        sig = fd.read(16)

    bsig = sig[0:4]
    zipsig = bytes(b'PK\x03\x04')
    rarsig = bytes(b'Rar!')

    if bsig == zipsig:
        return 1

    if sig[0:4] == rarsig:
        return 2

    return None


def get_image_fns(ao):
    """ - Given ao (either rarfile or zipfile archive object)
    - return a sorted list of files that has an image ext and is > 0 bytes
    """
    return [img for img in sorted(ao.infolist(), key=lambda x: x.filename) if img.file_size > 0 and is_image_ext(img.filename)]


def is_image_ext(fn):
    """ Returns true if the ext is any of the likely jpg/gif/png files. """
    bp, ext = os.path.splitext(fn)
    ext = ext.lower()

    return ext in ['.jpg', '.jpeg', '.jpe', '.gif', '.png']


def extract_cover_thumb(ao):
    """ Given ao (rar/zip file archive object)
    - Get the list of sorted image fns
    - Extract the first from the list
    """
    allrfi = get_image_fns(ao)
    num_pages = len(allrfi)
    if num_pages == 0:
        return (0, None)

    rfi = allrfi[0]
    tmpfn = rfi.filename
    with ao.open(tmpfn) as sf:
        return (num_pages, BytesIO(sf.read()))

def extract_comicinfo(ao):
    for aoitem in ao.infolist():
        if aoitem.filename.lower() == 'comicinfo.xml':
            with ao.open(aoitem, 'r') as archread:
                return archread.read()
    return None
    
def find_comicinfo(fn):
    atype = identify_arch(fn)
    try:
        if atype == 1:
            with zipfile.ZipFile(fn) as ao:
                xml = extract_comicinfo(ao)
        elif atype == 2:
            with rarfile.RarFile(fn) as ao:
                xml = extract_comicinfo(ao)
        else:
            return None
    except:
        traceback.print_exc(file=sys.stdout)
        return None
    
    return xml

def extract_all_images(ao, outdir, imgpfx=''):
    allrfi = get_image_fns(ao)
    ifiles = []
    page = 0

#    numlen = math.trunc(math, log10(len(allrfi))) + 1
    num_extracted = 0

    for rfi in allrfi:
        tbase, tmpext = os.path.splitext(rfi.filename)
        tmpext = tmpext.lower()

        page += 1
        tfn = '%s%04d%s' % (imgpfx, page, tmpext)
        ofn = os.path.join(outdir, tfn)

#        print(ofn)
        with ao.open(rfi, 'r') as archread:
            with open(ofn, 'wb') as fd:
                fd.write(archread.read())
                num_extracted += 1
                ifiles.append(ofn)

#    print("Extracted %d pages of to %s." % (num_extracted, outdir))
    return ifiles

def extract_thumb(crl):
    cp, cid, reslist, image_script, iprocscr = crl
    num_pages = 0
    atype = identify_arch(cp)
    if atype is None:
        return {'error': True, 'message': 'invalid archive', 'path': cp}

    try:
        if atype == 1:
            with zipfile.ZipFile(cp) as ao:
                num_pages, sio = extract_cover_thumb(ao)
        elif atype == 2:
            with rarfile.RarFile(cp) as ao:
                num_pages, sio = extract_cover_thumb(ao)
        else:
            return {'error': True, 'cid': cid, 'message': 'Unrecognized archive format', 'path': cp}
        if (num_pages == 0):
            return {'error': True, 'cid': cid, 'message': 'This archive has no image files.', 'path': cp}
    except:
        traceback.print_exc(file=sys.stdout)
        return {'error': True, 'cid': cid, 'message': 'Caught exception while processing archive', 'path': cp}

    im = Image.open(sio)
    if im.mode in ['RGBA', 'LA']:
        background = Image.new(im.mode[:-1], im.size)
        background.paste(im, im.split()[-1])
        im = background
    elif im.mode in ('P'):
        im = im.convert('RGB')

    writtenlist = []
    tl = []
    natpath = None
    
    for tli in reslist:
        exact_resize = False
        rx, ry, opath = tli
        if (rx != 0):
            tgtratio = 1.0 * im.width / im.height
        
        thumbres = (rx, ry)
        w = im.width
        h = im.height
        
        if (rx != 0):
            nwid = round(tgtratio * ry)
            widdiff = abs(nwid - rx)
            if (widdiff < 6):
                log.info("Difference is only %d", widdiff)
                exact_resize = True
            else:
                log.info("Difference is %d", widdiff)
        else:
            sio.seek(0, 0)
#            print("Position: %d" % sio.tell())
            s = sio.read()
            with open(opath, 'wb') as fd:
                natpath = opath
                fd.write(s)
            t = (cid, opath)
            continue
        
        mkregthumb = True
        
        if not exact_resize and image_script != 0:
            if not os.path.exists(iprocscr):
                log.error("Requested the image script, but can't find it - it must be in your current directory.")
                return None
            else:
                log.debug("Making a script processed thumbnail for cid: %s", cid)
                if os.path.exists(iprocscr) and image_script != 0:
                    args = ['/bin/bash', iprocscr, '-T', '%dx%d' % (rx,ry), natpath, opath]
                    
                    process = subprocess.Popen(args, shell=False)
                    process.wait()
                    mkregthumb = False
        else:
            log.debug("Making regular olde thumbnails.")
        
        copyim = im.copy()
        w = copyim.width
        h = copyim.height
        ratio = (1.0) * w / h
        rot = 0

        if (ratio > 1.15):
            rot = 90
            if mkregthumb:
                rcopyim = copyim.rotate(rot, Image.BICUBIC, 1)
                if exact_resize:
                    rcopyim = rcopyim.resize(thumbres, resample = Image.LANCZOS)
                else:
                    rcopyim.thumbnail(thumbres)
                rcopyim.save(opath, quality=85)
        else:
            if mkregthumb:
                if exact_resize:
                    copyim = copyim.resize(thumbres, resample = Image.LANCZOS)
                else:
                    copyim.thumbnail(thumbres)
                copyim.save(opath, quality=85)

    resd = {'error': False, 'cid': cid, 'num_pages': num_pages, 'owidth': w, 'oheight': h, 'ratio': ratio, 'twidth': thumbres[0], 'theight': thumbres[1], 'rot': rot, 'path': cp, 'tpath': opath}

#    print("Saved thumb: %s" % opath)
    return resd


def extract_archive(cp, temppath, pfx):
    atype = identify_arch(cp)
    ifiles = []
    if atype is None:
        return {'error': True, 'message': 'invalid archive', 'path': cp}

    try:
        if atype == 1:
            with zipfile.ZipFile(cp) as ao:
                ifiles = extract_all_images(ao, temppath, pfx)
        elif atype == 2:
            with rarfile.RarFile(cp) as ao:
                ifiles = extract_all_images(ao, temppath, pfx)
        else:
            raise (ValueError, "Invalid archive type: %d" % atype)
            return {'error': True, 'message': 'Unrecognized archive format', 'path': cp}
    except:
        raise ((ValueError, "Broken / Illegal file in archive."))
        traceback.print_exc(file=sys.stdout)
        return {'error': True, 'message': 'Caught exception while processing archive', 'path': cp}

    return ifiles
    
def get_archfiles(srcarch):
    try:
        if atype == 1:
            with zipfile.ZipFile(cp) as ao:
                return (ao, [ ai for ai in sorted(ai.ZipInfo(), key=lambda x: x.filename) if ai.file_size > 0 and is_image_ext(ai.filename)])
        elif atype == 2:
            with rarfile.RarFile(cp) as ao:
                return (ao, [ai for ai in sorted(ai.RarInfo(),key=lambda x: x.filename) if ai.file_size > 0 and is_image_ext(ai.filename)])
    except:
        traceback.print_exc(file=sys.stdout)
        raise (ValueError, "The archive is corrupt.")
