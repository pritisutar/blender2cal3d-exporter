CAL3D_VERSION = 1100	

class Cal3DSkeleton(object):
	BONES= {}
	__slots__ = 'bones'
	def __init__(self):
		import bpy,struct,math,os,time,sys,mathutils
		self.bones = []
	def writeCal3D(self, file):
		
		#rebuild skeleton index before writing
		self.rebuildBonesIndices();
			
		buff=('<?xml version="1.0"?>\n')
		#910buff+=('<HEADER MAGIC="XSF" VERSION="%i"/>\n' % CAL3D_VERSION)
		#buff+=('<SKELETON NUMBONES="%i">\n' % len(self.bones))
		buff+=('<SKELETON MAGIC="XSF" VERSION="%i" ' % CAL3D_VERSION)
		buff+=('NUMBONES="%i">\n' % len(self.bones))
		i=0;
		for item in self.bones:
			buff+=item.writeCal3D(file)
		buff+=('</SKELETON>\n')
		file.write(bytes(buff, 'UTF-8'));	
	
	def to_cal3d_binary(self, file):
				from array import array
				
				s = b'CSF\0'
				ar = array('b', list(s))
				ar.tofile(file)

				ar = array('L', [1100,
												 len(self.bones)])
				ar.tofile(file)

				for bn in self.bones:
						bn.to_cal3d_binary(file)
		
	def purgeUseLessBones(self)	:
		print("oldsize"+str(len(self.bones)))
		id=0
		while id< len(self.bones):#id in range(0,len(self.bones)): 
			try:b=self.bones[id] #prevent outofrange
			except:
				id=id+1
				continue
			id=id+1		
			if b.isUseLess():
					#TODO:remove from 
					self.killBoneWithChildren(b)
					self.rebuildBonesIndices()
					id=0
						
			
		self.rebuildBonesIndices()
		
		print("newsize"+str(len(self.bones)))
		

		
	def removeBoneFromSkelByName(self,name):
		#for item in self.bones:
		#	item.removeBoneByName(name)
		tokill=self;
		while not tokill is None:
			tokill=None;
			i=0
			for item in self.bones:
				if item.name ==name:
					#kill item
					print("founded in child")
					tokill=i
					
					break
				i+=1	
			if not tokill is None :
				print("killed %d"%len(self.bones))
				#del self.BONES[ self.bones[tokill].name]
				self.killwithAllChildren(tokill)
				self.rebuildBonesIndices()
				print("postkilled %d"%len(self.bones))
				
				
	def rebuildBonesIndices(self):
		i=0;
		for bone in self.bones: 
			bone.id=i
			i+=1

	def boneIndex(self,name):
		i=0;
		for bone in self.bones: 
			if bone.name==name:
				return i
			i+=1
		return -1;			
	
	def	killBoneWithChildren(self,bone):
		for item in bone.children:						
			self.killBoneWithChildren(item)
		
		#fix parent
		if	bone.cal3d_parent:
			#bone.cal3d_parent.children.remove(bone)
			k=0
			p=bone.cal3d_parent
			for c in p.children:
				if c.name==bone.name:
					break
				k+=1	
			
			del p.children[k]
		#dont forgot BONES IS STATIC member
		print("kill bone "+	str(bone.name.encode("utf8")))
		del self.BONES[ bone.name]
		del self.bones[self.boneIndex(bone.name)]
		self.rebuildBonesIndices()	

		
	def	killwithAllChildren(self,boneindex):
		for item in self.bones[boneindex].children:
			i=self.boneIndex(item.name)
						
			self.killwithAllChildren(i)
		
		#fix parent
		if	self.bones[boneindex].cal3d_parent:
			p=self.bones[boneindex].cal3d_parent
			k=0
			for c in p.children:
				if c.name==self.bones[boneindex].name:
					break
				k+=1	
			del p.children[k]
			
		#dont forgot BONES IS STATIC member
		del self.BONES[ self.bones[boneindex].name]
		del self.bones[boneindex]
		#self.rebuildBonesIndices()
