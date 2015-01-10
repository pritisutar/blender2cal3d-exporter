CAL3D_VERSION = 910

import bpy,struct,math,os,time,sys,mathutils
class Cal3DVertex(object):
	MAXBONEPERMESH=4
	WEIGHT_TRESHOLD=0.00	
	__slots__ = 'loc','normal','collapse_to','face_collapse_count','maps','influences','weight','id','hasweight'
	def __init__(self, loc, normal, maps, blend_influences):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMesh import Cal3DInfluence
		from .Cal3DMesh import Cal3DFace
		from .Cal3DMesh import Cal3DSpring
		from .Cal3DSkeleton import Cal3DSkeleton
		from .Cal3DBone import Cal3DBone
		self.loc    = mathutils.Vector(loc.copy())
		self.normal = mathutils.Vector(normal.copy())
		#print("CALVERTEX")
		#print(self.normal)
		self.collapse_to         = None
		self.face_collapse_count = 0
		self.maps       = maps
		self.weight = None
		
		#self.cloned_from = None
		#self.clones      = []
		self.hasweight=False
		self.id = -1
		
		if False: #len(blend_influences) == 0 or isinstance(blend_influences[0], Cal3DInfluence): 
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
			
			mincpt=0;
			floatinfluences=[]
			floatinfluences=blend_influences
			floatinfluences.sort( key=lambda inf: inf[1])  ;
			sum = 0.0
			if len(blend_influences) !=0:
				
				floatinfluences=[item for item in floatinfluences if  Cal3DSkeleton.BONES.get(item[0])]
				indexminweigth=max(0,len(floatinfluences)-self.MAXBONEPERMESH)
				if len(floatinfluences)>self.MAXBONEPERMESH :print(str(len(floatinfluences)-self.MAXBONEPERMESH)+" influences trashed with weight<"+str(floatinfluences[indexminweigth]))
										
				sum=0
				infcpt=len(floatinfluences)-1			
				while infcpt>=indexminweigth:
					sum +=floatinfluences[infcpt][1]
					infcpt=infcpt-1
				
				
				infcpt=len(floatinfluences)-1	
				totalinfluences=[]
				while  infcpt>=indexminweigth:
					bone_name=floatinfluences[infcpt][0]
					weight=floatinfluences[infcpt][1]
				#for bone_name, weight in floatinfluences:
					bone = Cal3DSkeleton.BONES.get(bone_name)
					if not bone: # keys
						print ("Couldnt find bone \""+bone_name+"\"")#+" which influences object "+ob.name)
						print(floatinfluences)
						continue
					
					if weight and sum:
						if weight/sum > self.WEIGHT_TRESHOLD:
							self.influences.append(Cal3DInfluence(bone, weight / sum))
							#bone.totalinfluence=1.0
							#totalinfluences.append(bone)
						else:
							#rebuild influences without this weight
							print("remove negligeable influence "+str(weight/sum)+"with  bone"+bone_name)
							sum-=weight
							#totalinfluences=[]							
							self.influences=[]	
							floatinfluences=[x for x in floatinfluences if x[0] != bone_name]
							indexminweigth=max(0,len(floatinfluences)-self.MAXBONEPERMESH)
							infcpt=len(floatinfluences)	
					infcpt=infcpt-1
				
				#Stat bone usage once vertex influences is set
				for boneinf in self.influences: boneinf.bone.maxinfluence=max(boneinf.weight,boneinf.bone.maxinfluence)
	
	def writeCal3D(self, file, matrix, matrix_normal,numtexcoord):
		
		if self.collapse_to:
			collapse_id = self.collapse_to.id
		else:
			collapse_id = -1
		buff=('\t\t<VERTEX ID="%i" NUMINFLUENCES="%i">\n' % \
				(self.id, len(self.influences)))
		daloc=matrix*mathutils.Vector((self.loc[0],self.loc[1],self.loc[2]))
		# Calculate global coords
		
		#print(matrix)
		buff+=('\t\t\t<POS>%.6f %.6f %.6f</POS>\n' % (daloc[0],daloc[1],daloc[2]))
		
		danormal=matrix_normal*self.normal;
		danormal.normalize()
		#print(danormal)
		buff+=('\t\t\t<NORM>%.6f %.6f %.6f</NORM>\n' % tuple(danormal ))
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
		
	def to_cal3d_binary(self, file, matrix, matrix_normal,numtexcoord):
				from array import array
				# sort influences by weights, in descending order
				#self.influences = sorted(self.influences, key=attrgetter('weight'), reverse=True)
				if self.collapse_to:
					collapse_id = self.collapse_to.id
				else:
					collapse_id = 0
				# normalize weights
				total_weight = 0.0
				for influence in self.influences:
						total_weight += influence.weight

				if total_weight != 1.0:
						for influence in self.influences:
								influence.weight /= total_weight
				daloc=matrix*mathutils.Vector((self.loc[0],self.loc[1],self.loc[2]))
				danormal=matrix_normal*self.normal;
				
				ar = array('f', [daloc[0],
												 daloc[1],
												 daloc[2],
												danormal[0],
												 danormal[1],
												 danormal[2]])
				ar.tofile(file)

				ar = array('L', [collapse_id,
												 self.face_collapse_count]) 
				ar.tofile(file)

				for i,mp in enumerate(self.maps):
						ar=array('f', [self.maps[i][0],1.0-self.maps[i][1]])
						ar.tofile(file)					
				ar = array('L', [len(self.influences)])
				ar.tofile(file)

				for ic in self.influences:
						ic.to_cal3d_binary(file)
						
				if self.hasweight:
						ar = array('f', [self.weight])
						ar.tofile(file) # writes the weight as a float for cloth hair animation (0.0 == rigid)
