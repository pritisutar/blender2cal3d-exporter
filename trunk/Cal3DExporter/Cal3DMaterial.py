CAL3D_VERSION = 1100
import bpy,struct,math,os,time,sys,mathutils
#problem with multiple texture material
class Cal3DMaterial(object):
	# keys are (mat.name, img.name)
	MATERIALS={}
	__slots__ = 'amb', 'diff', 'spec', 'shininess', 'maps_filenames', 'id'
	def __init__(self, blend_world, blend_material, blend_images):
		
		# Material Settings
		if blend_world:		amb = [ int(c*255) for c in blend_world.ambient_color ]
		else:				amb = [0,0,0] # Default value
		
		if blend_material:
			self.amb  = tuple([int(c*blend_material.ambient) for c in amb] + [255])
			self.diff = tuple([int(c*255) for c in blend_material.diffuse_color*blend_material.diffuse_intensity ] + [int(blend_material.alpha*255)])
			self.spec = tuple([int(c*255) for c in blend_material.specular_color*blend_material.specular_intensity ] + [int(blend_material.alpha*255)])
			self.shininess = (float(blend_material.specular_hardness)-1)/0.510 #from 1:511 to 0:1000...quite arbitrary
		else:
			print("NO MATERIAL USE DEFAULT ONE")
			self.amb  = tuple(amb + [255])
			self.diff = (255,255,255,255)
			self.spec = (255,255,255,255)
			self.shininess = 1.0
		
		self.maps_filenames = []
		#for image in blend_images:
			#if image:
				#print("image")
				#print(image) no multi tex for the moement
		#if blend_images :
		#	if blend_images!=blend_material.name:
		#		self.maps_filenames.append( blend_images.split('\\')[-1].split('/')[-1] )
		for blend_image in blend_images :
			if blend_image!=blend_material.name:
				self.maps_filenames.append( blend_image.split('\\')[-1].split('/')[-1] )
		#print( blend_images)
		self.id = len(self.MATERIALS)
		#self.MATERIALS[blend_material, blend_images] = self
	
	# new xml format
	def writeCal3D(self, file):
		buff='<?xml version="1.0"?>\n'
		#buff+=('<HEADER MAGIC="XRF" VERSION="%i"/>\n' % CAL3D_VERSION)
		#buff+=('<MATERIAL NUMMAPS="%s">\n' % len(self.maps_filenames))
		buff+=('<MATERIAL MAGIC="XRF" VERSION="%i" ' % CAL3D_VERSION)
		buff+=('NUMMAPS="%s">\n' % len(self.maps_filenames))
		buff+=('\t<AMBIENT>%i %i %i %i</AMBIENT>\n' % self.amb)
		buff+=('\t<DIFFUSE>%i %i %i %i</DIFFUSE>\n' % self.diff)
		buff+=('\t<SPECULAR>%i %i %i %i</SPECULAR>\n' % self.spec)
		buff+=('\t<SHININESS>%.6f</SHININESS>\n' % self.shininess)
		
		for map_filename in self.maps_filenames:
			#print(map_filename)
			buff+=('\t<MAP>%s.tga</MAP>\n' % map_filename)
		
		buff+=('</MATERIAL>\n')
		file.write(bytes(buff, 'UTF-8'))
	def to_cal3d_binary(self, file):
		from array import array

		s = b'CRF\0'
		ar = array('b', list(s))
		ar.tofile(file)

		ar = array('L', [1100])
		ar.tofile(file)

		ar = array('B', [self.ambient.r,
		 self.ambient.g,
		 self.ambient.b,
		 self.ambient.a,
										 self.diffuse.r,
		 self.diffuse.g,
		 self.diffuse.b,
		 self.diffuse.a,
										 self.specular.r,
		 self.specular.g,
		 self.specular.b,
		 self.specular.a])
		ar.tofile(file)

		ar = array('f', [self.shininess])
		ar.tofile(file)

		ar = array('L', [len(self.maps_filenames)])
		ar.tofile(file)

		for map_filename in self.maps_filenames:
				map_filename += '\0' # all strings end in null
				ar = array('L', [len(map_filename)])
				ar.tofile(file)
				
				ar = array('b', list(map_filename.encode("utf8")))
				ar.tofile(file)
