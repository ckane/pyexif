#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import json
import os
import re
import subprocess
import sys


def _install_exiftool_info():
	print  """
Cannot find 'exiftool'.

The ExifEditor class requires that the 'exiftool' command-line
utility is installed in order to work. Information on obtaining
this excellent utility can be found at:

http://www.sno.phy.queensu.ca/~phil/exiftool/
"""


def _runproc(cmd):
	if not _EXIFTOOL_INSTALLED:
		_install_exiftool_info()
		raise RuntimeError("Running this class requires that exiftool is installed")
	pipe = subprocess.PIPE
	proc = subprocess.Popen([cmd], shell=True, stdin=pipe, stdout=pipe,
			stderr=pipe, close_fds=True)
	proc.wait()
	err = proc.stderr.read()
	if err:
		raise RuntimeError(err)
	else:
		return proc.stdout.read()


# Test that the exiftool is installed
_EXIFTOOL_INSTALLED = True
try:
	out = _runproc("exiftool some_dummy_name.jpg")
except RuntimeError as e:
	# If the tool is installed, the error should be 'File not found'.
	# Otherwise, assume it isn't installed.
	err = "{0}".format(e).strip()

	print "ERR", err
	if err != "File not found: some_dummy_name.jpg":
		_EXIFTOOL_INSTALLED = False
		_install_exiftool_info()



class ExifEditor(object):
	def __init__(self, photo=None, save_backup=False):
		self.save_backup = save_backup
		if not save_backup:
			self._optExpr = "-overwrite_original_in_place"
		else:
			self._optExpr = "-overwrite_original_in_place"
		if photo is None:
			self.photo = "/Users/ed/Desktop/TEST.JPG"
		else:
			self.photo = photo
		# Tuples of (degrees, mirrored)
		self.rotations = {
				0: (0, 0),
				1: (0, 0),
				2: (0, 1),
				3: (180, 0),
				4: (180, 1),
				5: (90, 1),
				6: (90, 0),
				7: (270, 1),
				8: (270, 0)}
		self.invertedRotations = dict([[v, k] for k, v in self.rotations.items()])
		self.rotationStates = {0: (1, 2), 90: (5, 6),
				180: (3, 4), 270: (7, 8)}
		self.mirrorStates = (2, 4, 5, 7)
		# DateTime patterns
		self._datePattern = re.compile("\d{4}:[01]\d:[0-3]\d$")
		self._dateTimePattern = re.compile("\d{4}:[01]\d:[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d$")
		super(ExifEditor, self).__init__()


	def rotateCCW(self, num=1):
		"""Rotate left in 90 degree incrementss"""
		self._rotate(-90 * num)


	def rotateCW(self, num=1):
		"""Rotate right in 90 degree incrementss"""
		self._rotate(90 * num)


	def _rotate(self, deg):
		currOrient = self.getTag("Orientation#")
		currRot, currMirror = self.rotations[currOrient]
		dummy, newRot = divmod(currRot + deg, 360)
		newOrient = self.invertedRotations[(newRot, currMirror)]
		self._setOrientation(newOrient)


	def mirrorVertically(self):
		currOrient = self.getTag("Orientation#")
		currRot, currMirror = self.rotations[currOrient]
		newMirror = currMirror ^ 1
		newOrient = self.invertedRotations[(currRot, newMirror)]
		self._setOrientation(newOrient)


	def mirrorHorizontally(self):
		# First, rotate 180
		self.rotateCW(2)
		currOrient = self.getTag("Orientation#")
		currRot, currMirror = self.rotations[currOrient]
		newMirror = currMirror ^ 1
		newOrient = self.invertedRotations[(currRot, newMirror)]
		self._setOrientation(newOrient)


	def addKeyword(self, kw):
		self.addKeywords([kw])


	def addKeywords(self, kws):
		kws = ["-iptc:keywords+={0}".format(kw) for kw in kws]
		kwopt = " ".join(kws)
		cmd = """exiftool {self._optExpr} {kwopt} "{self.photo}" """.format(**locals())
		_runproc(cmd)


	def getKeywords(self):
		ret = self.getTag("Keywords")
		if not ret:
			return []
		if isinstance(ret, basestring):
			return [ret]
		return ret


	def setKeywords(self, kws):
		self.clearKeywords()
		self.addKeywords(kws)


	def clearKeywords(self):
		try:
			self.setTag("Keywords", "")
		except RuntimeError as e:
			# Returns an errror if there were no keywords
			print e


	def getTag(self, tag):
		cmd = """exiftool -j -{tag} "{self.photo}" """.format(**locals())
		out = _runproc(cmd)
		info = json.loads(out)[0]
		ret = info.get(tag)
		return ret


	def setTag(self, tag, val):
		if not isinstance(val, (list, tuple)):
			val = [val]
		vallist = ["-{0}={1}".format(tag, v) for v in val]
		valstr = " ".join(vallist)
		cmd = """exiftool {self._optExpr} {valstr} "{self.photo}" """.format(**locals())
		out = _runproc(cmd)


	def setOriginalDateTime(self, dttm=None):
		"""Set the image's original date/time (i.e., when the picture
		was 'taken') to the passed value. If no value is passed, set
		it to the current datetime.
		"""
		self._setDateTimeField("DateTimeOriginal", dttm)


	def setModificationDateTime(self, dttm=None):
		"""Set the image's modification date/time to the passed value.
		If no value is passed, set it to the current datetime (i.e.,
		like 'touch'.
		"""
		self._setDateTimeField("FileModifyDate", dttm)


	def _setDateTimeField(self, fld, dttm):
		if dttm is None:
			dttm = datetime.datetime.now()
		# Convert to string format if needed
		if isinstance(dttm, (datetime.datetime, datetime.date)):
			dtstring = dttm.strftime("%Y:%m:%d %H:%M:%S")
		else:
			dtstring = self._formatDateTime(dttm)
		cmd = """exiftool {self._optExpr} -{fld}='{dtstring}' "{self.photo}" """.format(**locals())
		_runproc(cmd)


	def _formatDateTime(self, dt):
		if self._datePattern.match(dt):
			# Add the time portion
			return "{0} 00:00:00".format(dt)
		elif self._dateTimePattern.match(dt):
			# Leave as-is
			return dt
		else:
			raise ValueError("Incorrect datetime value '{0}' received".format(dt))


	def _setOrientation(self, val):
		"""Orientation codes:
			   Rot	Img
			1: 0	Normal
			2: 0	Mirrored
			3: 180	Normal
			4: 180	Mirrored
			5: +90	Mirrored
			6: +90	Normal
			7: -90	Mirrored
			8: -90	Normal
		"""
		cmd = """exiftool {self._optExpr} -Orientation#='{val}' "{self.photo}" """.format(**locals())
		_runproc(cmd)




def main():
	print getKeywords()


if __name__ == "__main__":
	main()