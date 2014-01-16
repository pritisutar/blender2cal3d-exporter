CAL3D_VERSION = 910

class Cal3DBone(object):
	#BONES= {}
	__slots__ = 'blendbone','translation_absolute','rotation_absolute','head', 'tail', 'name', 'cal3d_parent', 'loc','child_loc', 'quat', 'children', 'matrix', 'lloc', 'lquat', 'id','bonespace','maxinfluence'
	def __init__(self, skeleton, blend_bone, cur_arm_matrix, cal3d_parent=None,armparent=None,isHacked=False):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DSkeleton import Cal3DSkeleton
		#global BONES
		self.blendbone=blend_bone
		self.bonespace=blend_bone.matrix.copy().to_4x4()
		#mymatislocal
		arm_matrix=cur_arm_matrix.copy()
		head = blend_bone.head.copy()
		tail = blend_bone.tail.copy()
		quat =None
		self.maxinfluence=0.0
		self.name   = blend_bone.name
		
		if cal3d_parent:
			if not blend_bone.parent:
				#aramture merging
				#armmatrix=armparent.matrix_world*arm_matrix.inverted()
				tmat=cal3d_parent.matrix.copy() #global parent matrix
				#tmat=armparent.matrix_world.inverted()*tmat #less parent armature transform
				tmat.invert()
				
				
				#self.hackingbonespacetrans=	 armparent.matrix_world*arm_matrix.inverted()	  
				#loc = head
				quat = ( tmat*self.bonespace).to_quaternion();
				#quat = ( self.hackingbonespacetrans*self.bonespace).to_quaternion();
				#print("TODO must hack bonespace (blend_bone.matrix)recursivly for all child")
				#self.bonespace=cal3d_parent.bonespace*self.bonespace
				cal3d_parent.children.append(self)
			else:
				quat =self.bonespace.to_quaternion()	
            # Compute the translation from the parent bone's head to the child
            # bone's head, in the parent bone coordinate system.
            # The translation is parent_tail - parent_head + child_head,
            # but parent_tail and parent_head must be converted from the parent's parent
            # system coordinate into the parent system coordinate.
			mymat= cal3d_parent.quat.to_matrix() #blend_bone.parent.matrix.copy();
			mymat.invert();
			parent_head=mymat*cal3d_parent.head
			
			parent_tail=mymat*cal3d_parent.tail
			
			if  blend_bone.parent:
				parent_tail=parent_tail+ head # vector_add(parent_tail, head)
			else:
				tmat=cal3d_parent.matrix.copy() #global parent matrix
			#tmat=armparent.matrix_world.inverted()*tmat #less parent armature transform
				tmat.invert()
				head = tmat*(head-cal3d_parent.blendbone.tail_local )#point_by_matrix(head, arm_matrix)
				tail = tmat*(tail-cal3d_parent.blendbone.tail_local)
				head = arm_matrix*head #point_by_matrix(head, arm_matrix)
				tail = arm_matrix*tail
				parent_tail=parent_tail+ (head)
			# DONE!!!
		   
			parentheadtotail = parent_tail-parent_head 
			#if not blend_bone.parent:
				#parentheadtotail=armparent.matrix_world*parentheadtotail
				#parent_tail=parent_tail+ head 
			loc=parentheadtotail; 
			
			
			
		else:
            # Apply the armature's matrix to the root bones
			head = arm_matrix*head #point_by_matrix(head, arm_matrix)
			tail = arm_matrix*tail
			          
			loc = head
			quat = (arm_matrix*self.bonespace).to_quaternion();
			
		self.head = head
		self.tail = tail
		
		self.cal3d_parent = cal3d_parent
		
		self.loc = loc
		self.quat = quat
		self.children = []
		
		self.matrix=quat.to_matrix().to_4x4().copy();
		self.matrix[3][0] += loc[0]
		self.matrix[3][1] += loc[1]
		self.matrix[3][2] += loc[2]
		
		
		if cal3d_parent:
			self.matrix = cal3d_parent.matrix*self.matrix
		#self.matrix = mathutils.Matrix(arm_matrix) * mathutils.Matrix(blend_bone.matrix_local) 
		# lloc and lquat are the bone => model space transformation (translation and rotation).
		# They are probably specific to Cal3D.
		
		#mymat2=self.matrix.inverted()
		#self.lloc =mathutils.Vector((mymat2[3][0], mymat2[3][1], mymat2[3][2]))
		#self.lquat = mymat2.to_quaternion();
		
		# Cal3d does the vertex deform calculation by:
		#   translationBoneSpace = coreBoneTranslationBoneSpace * boneAbsRotInAnimPose + boneAbsPosInAnimPose
		#   transformMatrix = coreBoneRotBoneSpace * boneAbsRotInAnimPose
		#   v = mesh * transformMatrix + translationBoneSpace
		# To calculate "coreBoneTranslationBoneSpace" (ltrans) and "coreBoneRotBoneSpace" (lquat)
		# we invert the absolute rotation and translation.
		self.translation_absolute = self.loc.copy()
		self.rotation_absolute = self.quat.copy()
		
		if self.cal3d_parent:
			self.translation_absolute.rotate(self.cal3d_parent.rotation_absolute)
			self.translation_absolute += self.cal3d_parent.translation_absolute

			self.rotation_absolute.rotate(self.cal3d_parent.rotation_absolute)
			self.rotation_absolute.normalize()
	
		self.lquat = self.rotation_absolute.inverted()
		self.lloc = -self.translation_absolute
		self.lloc.rotate(self.lquat)
		
		
		self.id = len(skeleton.bones)
		
		skeleton.bones.append(self)		
		Cal3DSkeleton.BONES[self.name] = self
		
		if len(blend_bone.children)<1 :	return
		
		
		for blend_child in blend_bone.children:
			#check for cyclein skeleton to define which bone is the father
			try:
				child=Cal3DSkeleton.BONES[blend_child.name];
			except:
				#dirty: check lenght of bone in order to select only the shortest (avoid artefact for specific models...
		
				#if blend_child.name[0:9]!='Root_Fing': #Filter here
				#if blend_child.name[0:2]!='IK':
				self.children.append(Cal3DBone(skeleton, blend_child, arm_matrix, self,armparent))
		
		
			
	def removeBoneByName(self,name):
		print("removeBoneByName %s %s\n"%(self.name,name))
		if False: #self.name==name :
			print("found")
			self.killAllChildren()
			print("return to caller never happen!!!!!")	
			#return True;
		else :
			tokill=self;
			while not tokill is None:
				tokill=None;
				i=0
				for item in self.children:
					if item.name ==name:
						#kill item
						print("founded in child")
						tokill=item
						item.killAllChildren()
						#break
					i+=1	
				if not tokill is None :
					print("killed %d"%len(self.children))
					self.children.remove(tokill)
					del Cal3DSkeleton.BONES[tokill.name]
					print("postkilled %d"%len(self.children))
			#return False;		
					
	def isUseLess(self):
		if self.maxinfluence==0:
			for child in self.children:
				if not child.isUseLess(): return False
			return True	
		else: return False	

		
	def killAllChildren(self):
		print("killAllChildren %s \n"%(self.name))
	
		tokill=self;
		while not tokill is None:
			print("tokillloop")
			tokill=None;
			i=0
			for item in self.children:
				print("killAllChildren in self.children")
				if len(item.children)==0:
					tokill=item
					#break
				else :
					item.killAllChildren()
				i+=1
			if not tokill is None:	
				print("killed")
				self.children.remove(tokill)
				del Cal3DSkeleton.BONES[tokill.name]
				

	def writeCal3D(self, file):
		buff=('\t<BONE ID="%i" NAME="%s" NUMCHILD="%i">\n' % \
				(self.id, self.name, len(self.children)))
		# We need to negate quaternion W value, but why ?
		buff+=('\t\t<TRANSLATION>%.6f %.6f %.6f</TRANSLATION>\n' % \
				 (self.loc[0], self.loc[1], self.loc[2]))
		if True:
			buff+=('\t\t<ROTATION>%.6f %.6f %.6f %.6f</ROTATION>\n' % \
				 (self.quat.x, self.quat.y, self.quat.z, -self.quat.w))
		
		buff+=('\t\t<LOCALTRANSLATION>%.6f %.6f %.6f</LOCALTRANSLATION>\n' % \
				 (self.lloc[0], self.lloc[1], self.lloc[2]))
		if  True:
			buff+=('\t\t<LOCALROTATION>%.6f %.6f %.6f %.6f</LOCALROTATION>\n' % \
				 (self.lquat.x, self.lquat.y, self.lquat.z, -self.lquat.w))
		
		if self.cal3d_parent:
			buff+=('\t\t<PARENTID>%i</PARENTID>\n' % self.cal3d_parent.id)
		else:
			buff+=('\t\t<PARENTID>%i</PARENTID>\n' % -1)
		
		for item in self.children:
			buff+=('\t\t<CHILDID>%i</CHILDID>\n' % item.id)
			
		buff+=('\t</BONE>\n')
		return buff
		
	def to_cal3d_binary(self, file):
		from array import array
		name = str(self.name.encode("utf8"))
		print(name)
		name += '\0'
		ar = array('I', [len(name)])
		ar.tofile(file)
		
		ar = array('b', list(name.encode("utf8")))
		ar.tofile(file)


		ar = array('f', [self.loc[0],
						 self.loc[1],
						 self.loc[2],
						 self.quat.x,
						 self.quat.y,
						 self.quat.z,
						 -self.quat.w,

						 self.lloc[0],
						 self.lloc[1],
						 self.lloc[2],
						 self.lquat.x, 
						 self.lquat.y,
						 self.lquat.z,
						 -self.lquat.w])# Etory : need negate quaternion values

		ar.tofile(file)

		if self.cal3d_parent:
			ar = array('I', [self.cal3d_parent.id])
		else:
			ar = array('i', [-1])
		if self.children:
			ar.append(len(self.children))
			for ch in self.children:
				ar.append(ch.id)
		else:
			ar.append(0)
		ar.tofile(file)
