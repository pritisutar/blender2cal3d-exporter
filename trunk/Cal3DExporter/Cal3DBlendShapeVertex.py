class Cal3DBlendShapeVertex(object):
	__slots__ = 'locs','normals','collapse_to','face_collapse_count','maps','influences','weight','cloned_from','clones','id'
	def __init__(self, locs, normals, maps, blend_influences):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMesh import Cal3DInfluence
		from .Cal3DMesh import Cal3DFace
		from .Cal3DMesh import Cal3DSpring
		from .Cal3DSkeleton import Cal3DSkeleton
		self.locs    = locs
		self.normals = normals
		#print("CALVERTEX")
		#print(self.normal)
		self.collapse_to         = None
		self.face_collapse_count = 0
		self.maps       = maps
		self.weight = None
		
		self.cloned_from = None
		self.clones      = []
		
		self.id = -1
		
		if len(blend_influences) == 0 or isinstance(blend_influences[0], Cal3DInfluence): 
			# This is a copy from another vert
			self.influences = blend_influences
		else:
			# Pass the blender influences
			
			self.influences = []
			# should this really be a warning? (well currently enabled,
			# because blender has some bugs where it doesn't return
			# influences in python api though they are set, and because
			# cal3d<=0.9.1 had bugs where objects without influences
			# aren't drawn.
			#if not blend_influences:
			#	print 'A vertex of object "%s" has no influences.\n(This occurs on objects placed in an invisible layer, you can fix it by using a single layer)' 
			# sum of influences is not always 1.0 in Blender ?!?!
			sum = 0.0
			
			for bone_name, weight in blend_influences:
				if Cal3DSkeleton.BONES.get(bone_name):
					sum += weight
			
			for bone_name, weight in blend_influences:
				bone = Cal3DSkeleton.BONES.get(bone_name)
				if not bone: # keys
					print ("Couldnt find bone \""+bone_name+"\"")#+" which influences object "+ob.name)
					print(blend_influences)
					continue
				
				if weight:
					self.influences.append(Cal3DInfluence(bone, weight / sum))
	
	
	def writeCal3D(self, file, matrix, matrix_normal,numtexcoord):
		import bpy,struct,math,os,time,sys,mathutils
		if self.collapse_to:
			collapse_id = self.collapse_to.id
		else:
			collapse_id = -1
		buff=('\t\t<VERTEX ID="%i" NUMINFLUENCES="%i">\n' % \
				(self.id, len(self.influences)))

		buff+=('\t\t\t<BLENDVERT>\n')
		for blendshapeindex in range(0,len(self.locs)):
			daloc=matrix*mathutils.Vector((self.locs[blendshapeindex][0],self.locs[blendshapeindex][1],self.locs[blendshapeindex][2]))
			# Calculate global coords
		
			#print(matrix)
			buff+=('\t\t\t<POS>%.6f %.6f %.6f</POS>\n' % (daloc[0],daloc[1],daloc[2]))
		
			danormal=matrix_normal*self.normals[blendshapeindex];
			danormal.normalize()
			#print(danormal)
			buff+=('\t\t\t<NORM>%.6f %.6f %.6f</NORM>\n' % tuple(danormal ))
		buff+=('\t\t\t</BLENDVERT>\n')
		if collapse_id != -1:
			buff+=('\t\t\t<COLLAPSEID>%i</COLLAPSEID>\n' % collapse_id)
			buff+=('\t\t\t<COLLAPSECOUNT>%i</COLLAPSECOUNT>\n' % \
					 self.face_collapse_count)
		for i in range(numtexcoord):
			#revert v before writing
			#self.maps[i] = (self.maps[i][0], 1.0-self.maps[i][1])  #[1]=1.0-self.maps[i][1]
			buff+=('\t\t\t<TEXCOORD>%.6f %.6f</TEXCOORD>\n' % (self.maps[i][0],1.0-self.maps[i][1]))
		#for uv in self.maps:
			# we cant have more UV's then our materials image maps
			# check for this
			#buff+=('\t\t\t<TEXCOORD>%.6f %.6f</TEXCOORD>\n' % uv)
		
		for item in self.influences:
			buff+=item.writeCal3D(file)
		
		if self.weight != None:
			buff+=('\t\t\t<PHYSIQUE>%.6f</PHYSIQUE>\n' % len(self.weight))
		buff+=('\t\t</VERTEX>\n')
		return buff;
