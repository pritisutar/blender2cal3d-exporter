bl_info = { # changed from bl_addon_info in 2.57 -mikshaw
    "name": "Export Cal3d(.cfg)",
    "author": "J.Valentin",
    "version": (0,5,66),
    "blender": (2, 6, 2),
    "api": 31847,
    "location": "File > Export > Cal3d Skeletal Mesh/Animation Data(.cfg)",
    "description": "Export cal3d",
    "warning": "TODO Features: Collect IPO to avoid animation baking ",
    "wiki_url": "http://wiki.blender.org/",
    "tracker_url": "http://google.com",
    "category": "Import-Export"}	# changed from "Import/Export" -katsbits

# Enables LODs computation. LODs computation is quite slow, and the algo is
# surely not optimal :-(
LODS = 0 #not tested

CAL3D_VERSION = 1100
CHILD_ARMATURE_TRY=True

MESH_EXPORT_MODE='PREVIEW' #'RENDER')
# Scale the model (not supported by Soya).
DEBUG_KEYFRAME_EXPORT=False
DEBUGECLIPSE=False

#default parameters
INTERACTIVE_BONE_SELECTION=False
SCALE=1
FPS=16
WRITEBINARY=False
BAKEDEXPORT=False
EXPORTBLENDSHAPES=False
APPLY_MODIFIERS=True
EXPORTMESHES=True

#DIRTY GLOBALS
selected=None
blender_armature=None
file_only_noext=''
base_only =''
skeleton=None
meshes=[]
blend_meshes=[]
globfilename='' 
#Cal3DSkeleton.BONES = {} 
POSEBONES= {}
ALLARMATURES={}

#DEBUG
KEYFRAMEDBONES={}
KEYFRAMEARMATURES={}#Armatures already processed by recursion in order to avoid duplicate call to recursiveKeyframe



#########################################################################################
# Code starts here.
# The script should be quite re-useable for writing another Blender animation exporter.
# Most of the hell of it is to deal with Blender's head-tail-roll bone's definition.

import bpy,struct,math,os,time,sys,mathutils
from array import array

def cleanJapaneseString(v):
#convert not recognized character to ascii and suppress \xs
	utf8= str(v.encode('utf_8'))
	return utf8.replace('\\x','')[2:len(utf8.replace("\\x",""))-1]
	
#triangulate but mess with vertex order
#don't use it unless you have convex polygon meshes (but consider triangulate within blender it's more reliable)
def mesh_triangulate(me):
	import bmesh
	bm = bmesh.new()
	bm.from_mesh(me)
	bmesh.ops.triangulate(bm, faces=bm.faces)
	bm.to_mesh(me)
	bm.free()
	me.calc_normals()
	me.calc_tessface()





class Cal3DSpring(object):
	__slots__ = 'vertex1', 'vertex2', 'spring_coefficient', 'idlelength'
	def __init__(self, vertex1, vertex2):
		self.vertex1 = vertex1
		self.vertex2 = vertex2
		self.spring_coefficient = 0.0
		self.idlelength = 0.0
	
	def writeCal3D(self, file):
		return ('\t\t<SPRING VERTEXID="%i %i" COEF="%.6f" LENGTH="%.6f"/>\n' % \
					 (self.vertex1.id, self.vertex2.id, self.spring_coefficient, self.idlelength))
	def to_cal3d_binary(self, file):
                ar = array('L', [self.vertex1.index,   self.vertex2.index])
                ar.tofile(file)
                ar = array('f', [self.spring_coef,  self.idle_length])
                ar.tofile(file)


class Cal3DMorphTrack(object):
	__slots__ = 'morphTargetName', 'keyframes'
	def __init__(self, morphTargetName):
		self.morphTargetName      = morphTargetName
		self.keyframes = []

	def writeCal3D(self, file):
		buff=('\t<TRACK MORPHNAME="%s" NUMKEYFRAMES="%i">\n' %
				(self.morphTargetName, len(self.keyframes)))
		for item in self.keyframes:
			buff+=item.writeCal3D(file)
		buff+=('\t</TRACK>\n')
		return buff;
	def to_cal3d_binary(self, file):
		ar = array('b', list(self.morphTargetName.encode("utf8")))
		ar.tofile(file)
		ar = array('L', [len(self.keyframes)])
		ar.tofile(file)
		for kf in self.keyframes:
                        kf.to_cal3d_binary(file)                
		ar.tofile(file)	
		
class Cal3DMorphAnimation:
	def __init__(self, name, duration = 0.0):
		self.name     = name
		self.duration = duration
		self.tracks   = [] # Map bone names to tracks
	
	def writeCal3D(self, file):
		buff=('<?xml version="1.0"?>\n')
		buff+=('<ANIMATION MAGIC="XPF" VERSION="%i" ' % CAL3D_VERSION)
		buff+=('DURATION="%.6f" NUMTRACKS="%i">\n' % \
				 (self.duration, len(self.tracks)))
		#buff+=('<HEADER MAGIC="XPF" VERSION="%i"/>\n' % CAL3D_VERSION)
		#buff+=('<ANIMATION DURATION="%.6f" NUMTRACKS="%i">\n' % \
		#		 (self.duration, len(self.tracks)))
		
		for item in self.tracks:
			buff+=item.writeCal3D(file)
		buff+=('</ANIMATION>\n')
		file.write(bytes(buff, 'UTF-8'))
	def to_cal3d_binary(self, file):
		s = b'CPF\0'
		ar = array('b', list(s))
		ar.tofile(file)

		ar = array('L', [1100]) # this is the file version I was working from
		ar.tofile(file)
		# ar = array('L', [1300]) # one file version up from the documentation (with compression)
		# ar.tofile(file)
		ar = array('f', [self.duration])
		ar.tofile(file)
		ar = array('L', [len(self.tracks.values())#,0# flags for tracks Bit 0: 1 if compressed tracks
									 ]) 
		ar.tofile(file)
		#ar = array('L', [0]) # Bit 0: 1 if compressed tracks
		#ar.tofile(file)
		for tr in self.tracks.values(): # not sure what to do here yet
			tr.to_cal3d_binary(file)
                	
class Cal3DMorphKeyFrame(object):
	__slots__ = 'time', 'weight'
	def __init__(self, time, weight):
		self.time = time
		self.weight  = weight
		
	
	def writeCal3D(self, file):
		buff=('\t\t<KEYFRAME TIME="%.6f">\n' % self.time)
		buff+=('\t\t\t<WEIGHT>%.6f </WEIGHT>\n' % \
				 self.weight)
		
		buff+=('\t\t</KEYFRAME>\n')
		return buff
	def to_cal3d_binary(self, file):
                ar = array('f', [self.time,
                                                 self.weight])
                ar.tofile(file)
class Cal3DAnimation:
	def __init__(self, name, duration = 0.0):
		self.name     = name
		self.duration = duration
		self.tracks   = {} # Map bone names to tracks
	
	def writeCal3D(self, file):
		buff=('<?xml version="1.0"?>\n')
		buff+=('<ANIMATION MAGIC="XAF" VERSION="%i" ' % CAL3D_VERSION)
		buff+=('DURATION="%.6f" NUMTRACKS="%i">\n' % \
				 (self.duration, len(self.tracks)))
		#buff+=('<HEADER MAGIC="XAF" VERSION="%i"/>\n' % CAL3D_VERSION)
		#buff+=('<ANIMATION DURATION="%.6f" NUMTRACKS="%i">\n' % \
		#		 (self.duration, len(self.tracks)))
		
		for item in self.tracks.values():
			buff+=item.writeCal3D(file)
		buff+=('</ANIMATION>\n')
		file.write(bytes(buff, 'UTF-8'))
	def to_cal3d_binary(self, file):
			s = b'CAF\0'
			ar = array('b', list(s))
			ar.tofile(file)

			ar = array('L', [1100]) # this is the file version I was working from
			ar.tofile(file)
			# ar = array('L', [1300]) # one file version up from the documentation (with compression)
			# ar.tofile(file)
			ar = array('f', [self.duration])
			ar.tofile(file)
			ar = array('L', [len(self.tracks.values())#,0# flags for tracks Bit 0: 1 if compressed tracks
											 ]) 
			ar.tofile(file)
			#ar = array('L', [0]) # Bit 0: 1 if compressed tracks
			#ar.tofile(file)
			for tr in self.tracks.values(): # not sure what to do here yet
				tr.to_cal3d_binary(file)
class Cal3DTrack(object):
	__slots__ = 'bone', 'keyframes'
	def __init__(self, bone):
		self.bone      = bone
		self.keyframes = {}

	def writeCal3D(self, file):
		buff=('\t<TRACK BONEID="%i" NUMKEYFRAMES="%i">\n' %
				(self.bone.id, len(self.keyframes.values())))
		k=sorted(self.keyframes.values(),key=lambda key: key.time)
		for item in k:
			buff+=item.writeCal3D(file)
		buff+=('\t</TRACK>\n')
		return buff;
	def to_cal3d_binary(self, file):
		
		k=sorted(self.keyframes.values(),key=lambda key: key.time)
		ar = array('L', [self.bone.id, len(self.keyframes.values())])
		ar.tofile(file)
		for kf in k:
			kf.to_cal3d_binary(file)                
	
	#linear keyframe interpoaltion
	def evaluate(self,time):
		#assert keyframes sorted
		kframes=[c for c in self.keyframes.values()] #BAD...but don't know how to do it wiser 4 the moement
		l=len(kframes)
		if l<2 :return mathutils.Matrix()
		index=1
		while kframes[index].time<time and index<l:index=index+1
				
		#test last keyframe
		if index==l:
			#return trans at l-1
			m=kframes[index-1].quat.to_matrix().to_4x4()
			mat_trans = mathutils.Matrix.Translation(kframes[index-1].loc)
			return m
		
		index0=index-1
		#test case of kf duplication ..never happense because of the map
		#while kframes[index0].time==kframes[index].time 
		
		deltat=(time-kframes[index-1].time)/(kframes[index].time-kframes[index-1].time)
		#m=mathutils.Matrix()
		m=kframes[index-1].quat.slerp(kframes[index].quat,deltat).to_matrix().to_4x4()
		trans=(1-deltat)*kframes[index-1].loc+deltat*kframes[index].loc
		
		mat_trans = mathutils.Matrix.Translation(trans)
		return m#mat_trans*
			
			
			
class Cal3DKeyFrame(object):
	__slots__ = 'time', 'loc', 'quat'
	def __init__(self, time, loc, quat):
		self.time = time
		self.loc  = loc.copy()
		self.quat = quat.copy()
	
	def writeCal3D(self, file):
		buff=('\t\t<KEYFRAME TIME="%.6f">\n' % self.time)
		buff+=('\t\t\t<TRANSLATION>%.6f %.6f %.6f</TRANSLATION>\n' % \
				 (self.loc.x, self.loc.y, self.loc.z))
		# We need to negate quaternion W value, but why ?
		buff+=('\t\t\t<ROTATION>%.6f %.6f %.6f %.6f</ROTATION>\n' % \
				 (self.quat.x, self.quat.y, self.quat.z, -self.quat.w))
		buff+=('\t\t</KEYFRAME>\n')
		return buff
	def to_cal3d_binary(self, file):
                ar = array('f', [self.time,
                                                 self.loc.x,
                                                 self.loc.y,
                                                 self.loc.z,
                                                 self.quat.x,
                                                 self.quat.y,
                                                 self.quat.z,
                                                 -self.quat.w])
                ar.tofile(file)



def getBakedPoseData(ob_arm, start_frame, end_frame, ACTION_BAKE = False, ACTION_BAKE_FIRST_FRAME = True):
	'''
	NOT WORKING
	If you are currently getting IPO's this function can be used to
	ACTION_BAKE==False: return a list of frame aligned bone dictionary's
	ACTION_BAKE==True: return an action with keys aligned to bone constrained movement
	if ACTION_BAKE_FIRST_FRAME is not supplied or is true: keys begin at frame 1
	
	The data in these can be swaped in for the IPO loc and quat
	
	If you want to bake an action, this is not as hard and the ipo hack can be removed.
	'''
	
	# --------------------------------- Dummy Action! Only for this functon
	backup_action = ob_arm.animation_data.action
	#backup_frame = Blender.Get('curframe')
	
	
	DUMMY_ACTION_NAME = '~DONT_USE~'
	# Get the dummy action if it has no users
	try:
		new_action = bpy.data.actions[DUMMY_ACTION_NAME]
		if new_action.users:
			new_action = None
	except:
		new_action = None
	
	if not new_action:
		new_action = bpy.data.actions.new(DUMMY_ACTION_NAME)
		#new_action.fakeUser = False
	# ---------------------------------- Done
	
	Matrix = mathutils.Matrix
	Quaternion = mathutils.Quaternion
	Vector = mathutils.Vector
	POSE_XFORM= [Blender.Object.Pose.LOC, Blender.Object.Pose.ROT]
	
	# Each dict a frame
	bake_data = [{} for i in xrange(1+end_frame-start_frame)]
	
	pose=			ob_arm.getPose()
	armature_data=	ob_arm.getData();
	pose_bones=		pose.bones
	
	# --------------------------------- Build a list of arma data for reuse
	armature_bone_data = []
	bones_index = {}
	for bone_name, rest_bone in armature_data.bones.items():
		pose_bone = pose_bones[bone_name]
		rest_matrix = rest_bone.matrix['ARMATURESPACE']
		rest_matrix_inv = rest_matrix.copy().invert()
		armature_bone_data.append( [len(bones_index), -1, bone_name, rest_bone, rest_matrix, rest_matrix_inv, pose_bone, None ])
		bones_index[bone_name] = len(bones_index)
	
	# Set the parent ID's
	for bone_name, pose_bone in pose_bones.items():
		parent = pose_bone.parent
		if parent:
			bone_index= bones_index[bone_name]
			parent_index= bones_index[parent.name]
			armature_bone_data[ bone_index ][1]= parent_index
	# ---------------------------------- Done
	
	
	
	# --------------------------------- Main loop to collect IPO data
	frame_index = 0
	NvideoFrames= end_frame-start_frame
	for current_frame in xrange(start_frame, end_frame+1):
		if   frame_index==0: start=sys.time()
		#elif frame_index==15: print NvideoFrames*(sys.time()-start),"seconds estimated..." #slows as it grows *3
		elif frame_index >15:
			percom= frame_index*100/NvideoFrames
			#print "Frame %i Overall %i percent complete" % (current_frame, percom),
		ob_arm.action = backup_action
		#pose.update() # not needed
		Blender.Set('curframe', current_frame)
		#Blender.Window.RedrawAll()
		#frame_data = bake_data[frame_index]
		ob_arm.action = new_action
		###for i,pose_bone in enumerate(pose_bones):
		
		for index, parent_index, bone_name, rest_bone, rest_matrix, rest_matrix_inv, pose_bone, ipo in armature_bone_data:
			matrix= pose_bone.poseMatrix
			parent_bone= rest_bone.parent
			if parent_index != -1:
				parent_pose_matrix =		armature_bone_data[parent_index][6].poseMatrix
				parent_bone_matrix_inv =	armature_bone_data[parent_index][5]
				matrix=						matrix * parent_pose_matrix.copy().invert()
				rest_matrix=				rest_matrix * parent_bone_matrix_inv
			
			matrix=matrix * rest_matrix.copy().invert()
			pose_bone.quat=	matrix.toQuat()
			pose_bone.loc=	matrix.translationPart()
			if ACTION_BAKE==False:
				pose_bone.insertKey(ob_arm, 1, POSE_XFORM) # always frame 1
	 
				# THIS IS A BAD HACK! IT SUCKS BIGTIME BUT THE RESULT ARE NICE
				# - use a temp action and bake into that, always at the same frame
				#   so as not to make big IPO's, then collect the result from the IPOs
			
				# Now get the data from the IPOs
				if not ipo:	ipo = armature_bone_data[index][7] = new_action.getChannelIpo(bone_name)
			
				loc = Vector()
				quat  = Quaternion()
			
				for curve in ipo:
					val = curve.evaluate(1)
					curve_name= curve.name
					if   curve_name == 'LocX':  loc[0] = val
					elif curve_name == 'LocY':  loc[1] = val
					elif curve_name == 'LocZ':  loc[2] = val
					elif curve_name == 'QuatW': quat.w  = val
					elif curve_name == 'QuatX': quat.x  = val
					elif curve_name == 'QuatY': quat.y = val
					elif curve_name == 'QuatZ': quat.z  = val
			
				bake_data[frame_index][bone_name] = loc, quat
			else:
				if ACTION_BAKE_FIRST_FRAME: pose_bone.insertKey(ob_arm, frame_index+1,  POSE_XFORM)
				else:           pose_bone.insertKey(ob_arm, current_frame , POSE_XFORM)
		frame_index+=1
	#print "Baking Complete."
	#ob_arm.action = backup_action
	if ACTION_BAKE==False:
		#Blender.Set('curframe', backup_frame)
		return bake_data
	elif ACTION_BAKE==True:
		return new_action
	#else: print "ERROR: Invalid ACTION_BAKE %i sent to BPyArmature" % ACTION_BAKE

	


def new_name(file_noext,dataname, ext):
		return file_noext + '_' + dataname + ext
		
		
		
def export_cal3d(filename ):
	
	from .Cal3DMaterial import Cal3DMaterial
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	from .Cal3DMesh import Cal3DMesh
	from .Cal3DSubMesh import Cal3DSubMesh
	from .Cal3DVertex import Cal3DVertex
	global blender_armature
	global file_only_noext
	global skeleton
	global base_only
	global globfilename
	global selected
	#global Cal3DSkeleton.BONES 
	
	#bpy.ops.object.mode_set(mode='OBJECT')
	sce =bpy.context.scene;
	if not filename.endswith('.cfg'):
		filename += '.cfg'
	globfilename=filename
	file_only = globfilename.split('/')[-1].split('\\')[-1]
	file_only_noext = file_only.split('.')[0]
	base_only = globfilename[:-len(file_only)]
	

	

	# bpy.data.scenes.active
	blend_world = sce.world
	# ---- Export skeleton (armature) ----------------------------------------
	
	
	skeleton= Cal3DSkeleton()
	selected=bpy.context.selected_objects.copy()
	
	blender_armature = [ob for ob in bpy.context.selected_objects if ob.type == 'ARMATURE']
	#if len(blender_armature) > 1:	print "Found multiple armatures! using ",armatures[0].name
	if blender_armature:
		print("ARMATURE FOUND");
		#blender_armature = blender_armature[0]
	

	for arma in blender_armature:
		for arma in blender_armature:
			crawlAllArmaturesinPOSEBONES(arma)
		
	for arma in blender_armature:
		recursivCal3DBone(arma,skeleton)
	
	#just to know useless bones
	exportMeshes()
	#purge useless bones
	skeleton.purgeUseLessBones()
	
	if INTERACTIVE_BONE_SELECTION:	
		buildtempSkeleton((-1,0,0),skeleton) 
	else:	
		continuexport()	
	
	return
	

def exportMeshes(IsSimul=True):
# ---- Export Mesh data ---------------------------------------------------
	from .Cal3DMaterial import Cal3DMaterial
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	from .Cal3DMesh import Cal3DMesh
	from .Cal3DBlendShapeMesh import Cal3DBlendShapeMesh
		
	global skeleton
	global meshes 
	global blendmeshes
	global selected
	meshes = []
	blendmeshes=[]
	
	#bpy.ops.object.mode_set(mode='OBJECT')
	#bpy.context.scene.frame_set(bpy.context.scene.frame_start);
	for ob in  selected:
		print( "Processing mesh: "+ str(ob.name.encode("utf8"))+ ob.type )
		if ob.type != 'MESH':continue
		#print("mesh found in selection")
		#blend_mesh = ob.getData(mesh=1)
        #cloth case: generate spring system
		isCloth=False
		for mod in ob.modifiers:
			if mod.type=='CLOTH':isCloth=True
			if mod.type=='ARMATURE':mod.show_viewport=False #Set off armatures to bake meshes...reactiiviate it latter
		if isCloth:
			generateSpringSystem(ob)
			continue
		#ob.active_shape_key_index=1
		#if ob.active_shape_key!=None:ob.active_shape_key.value=1.0
		data=ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
		#mesh_triangulate(data)
		
		
		if not data.tessfaces or ob.name[0:3]=="Sim_":	 		continue
		
        
        #check for bounding volume 4 cloth with IK armature
		for ob2 in  selected:         
			if ob2.name=="Sim_"+ob.name:
				#TODO check if ob2 have a cloth modifier
				#	generateSpringSystem(data,ob2)
				#this mesh have a simulation mesh dual
					break
    
                #detect if mesh have shapekeys
		haveShapeKey=False
		saveshapekeyindex=ob.active_shape_key_index
		ob.active_shape_key_index=1
		if ob.active_shape_key!=None: haveShapeKey=True
		ob.active_shape_key_index=saveshapekeyindex
		
		if haveShapeKey and EXPORTBLENDSHAPES and not IsSimul:
			#parse keyshapes
			shapekeycpt=0
			ob.active_shape_key_index=shapekeycpt
			current_shapekey=ob.active_shape_key
			
			
			##For each shapekeys test existence (only way to know numbers of shapekeys???!!!:/)
			while current_shapekey!=None:
				#reset all shape keys (TODO ensure we're not in posemode in order not to break recorded animation)
				current_shapekey.value=0
				shapekeycpt=shapekeycpt+1
				ob.active_shape_key_index=shapekeycpt
				current_shapekey=ob.active_shape_key
				
			numBlendShape=shapekeycpt
			data=ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
			#mesh_triangulate(data)
			
			meshes.append( Cal3DMesh(ob,data , bpy.context.scene.world) )
			#temporary meshes create from shape keys 
			#blender_meshes=[]
			#index 0 is base shape
			#blender_meshes.append(ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE))	
			for shapekey_index in range(1,numBlendShape):
				ob.active_shape_key_index=shapekey_index
				ob.active_shape_key.value=1.0
				#self.blendshapes_names.append(ob.active_shape_key.name)
				#data=ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
				data=ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
				#mesh_triangulate(data)
				
				
				cmesh=Cal3DMesh(ob,data , bpy.context.scene.world) 
				cmesh.name=cmesh.name+"_"+ cleanJapaneseString(ob.active_shape_key.name)
				blendmeshes.append(cmesh)
				ob.active_shape_key.value=0.0
		else:
			meshes.append( Cal3DMesh(ob,data , bpy.context.scene.world) )
			#reset modifiers state
		for mod in ob.modifiers:
			if mod.type=='ARMATURE':mod.show_viewport=True	
			
def crawlAllArmaturesinPOSEBONES(B_armature):
	global POSEBONES
	global ALLARMATURES
	try:
		t=ALLARMATURES[B_armature.name]
	except:
		ALLARMATURES[B_armature.name]=B_armature
		for pbone in B_armature.data.bones.values():
			POSEBONES[pbone.name] = pbone
		for armachild in B_armature.children:#	RECURSION
			if armachild.type == 'ARMATURE':
				crawlAllArmaturesinPOSEBONES(armachild)
				
				
def getArmatureFromBone(bone):
	global ALLARMATURES
	try:
		for arma in ALLARMATURES.values():
			for b in arma.data.bones.values():
				if b.name==bone.name: return arma
	except:return None
	return None	
	
	
def recursivCal3DBone(B_armature,skeleton):
	global POSEBONES
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	#control parent  if it's a bones
	parentbone=None
	if B_armature.parent:
		if B_armature.parent.type=='ARMATURE':
			
			#theres's a parent bone
			parentname=B_armature.parent_bone
			BlenderParentBone=POSEBONES[parentname]
			try:
				parentbone=Cal3DSkeleton.BONES[parentname ] 
			except:	#but cal armature 's not created yet
				recursivCal3DBone(B_armature.parent,skeleton)
				parentbone=Cal3DSkeleton.BONES[parentname] 
				

	
	for pbone in B_armature.data.bones.values():
			#traverses bones
			for blender_bone in B_armature.data.bones:
				if not blender_bone.parent:						
					try:#if already exists do nothing
						bone=Cal3DSkeleton.BONES[blender_bone.name] 
					except:	
						Cal3DBone(skeleton, blender_bone,
						B_armature.matrix_world,
						parentbone,
						getArmatureFromBone(parentbone))
	
	for armachild in B_armature.children:#	RECURSION
		if armachild.type == 'ARMATURE':
					recursivCal3DBone(armachild,skeleton)
					
		
def recursiveKeyframing(B_armature	, animation, time, AllArmatures):
	global KEYFRAMEARMATURES
	global KEYFRAMEDBONES
	from .Cal3DMaterial import Cal3DMaterial
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	from .Cal3DMesh import Cal3DMesh
	from .Cal3DSubMesh import Cal3DSubMesh
	from .Cal3DVertex import Cal3DVertex
									
	try:
		temp = KEYFRAMEARMATURES[B_armature.name]
	except:	
		KEYFRAMEARMATURES[B_armature.name] = B_armature
		pose = B_armature.pose
		if DEBUG_KEYFRAME_EXPORT:print("recursivekeyfram" + B_armature.name)
		for bonename in B_armature.data.bones.keys():
			try:
				tb=KEYFRAMEDBONES[bonename]
			except:
				KEYFRAMEDBONES[bonename]=bonename
				try:
					bone = Cal3DSkeleton.BONES[bonename]  # look up cal3d_bone
				except:
					#if DEBUG_KEYFRAME_EXPORT:print("try to animate  a bone " + bonename + "from armature" + B_armature.name + "that is not part of the crawled bones: ")
					continue
				posebonemat = pose.bones[bonename].matrix.copy()  # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
				hasvirtualparent=False
				if bone.blendbone.parent :  # cal3d_parent :
				# need parentspace-matrix
					parentposemat = mathutils.Matrix()
					try:
						parentposemat = pose.bones[bone.cal3d_parent.name].matrix.copy()  # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
						parentposemat.invert()
						posebonemat = parentposemat * posebonemat 
					except:
						if DEBUG_KEYFRAME_EXPORT:print("WTF keyfram")
						continue  # forget this keyframe(should be set on an other armature
						
						
					
				else:
					
					if not bone.blendbone.parent:
						#B_armature=getArmatureFromBone(bone)
						if B_armature.parent:
							if B_armature.parent.type=='ARMATURE':#theres's a parent bone
								hasvirtualparent=True
								
					if hasvirtualparent:	
						if DEBUG_KEYFRAME_EXPORT:print("parent is from an other armature so find parent bone and chain transform with current bone")
						for arma in AllArmatures:
							try: 
							
							
								parentArmaMatrix=arma.matrix_world.copy();
								parentArmaMatrix.invert()
								parentposemat = mathutils.Matrix(arma.pose.bones[B_armature.parent_bone].matrix)
								curparent=None
								parentposemat.invert()
								
									
							
								
								
								
								calparent=Cal3DSkeleton.BONES[B_armature.parent_bone]
								#get global parent bon transform
								invparent=calparent.matrix.copy()
								inv=B_armature.matrix_world.copy()
								inv.invert()
								#invparent.invert()arma.matrix_world.inverted()*
								#posebonemat =   B_armature.matrix_world.inverted()*posebonemat 
								posebonemat =  parentposemat*B_armature.matrix_world *posebonemat
								#posebonemat =   B_armature.matrix_world*  posebonemat 
								if DEBUG_KEYFRAME_EXPORT:print("parent transformfor bone"+bone.name+"is in armature"+arma.name)
								break
							except:	continue
								
					else:
						posebonemat = B_armature.matrix_world * posebonemat
				#reverse order of multiplication!!!
				loc = mathutils.Vector((posebonemat[3][0],
				posebonemat[3][1],
				posebonemat[3][2],
				))
				
				rot = posebonemat.to_quaternion() 
				rot.normalize() 
				
				tposebonemat = pose.bones[bonename].matrix.copy()
				#loc = mathutils.Vector((tposebonemat[3][0],
				#tposebonemat[3][1],
				#tposebonemat[3][2],
				#))
				#if  not hasvirtualparent:
				loc=posebonemat.to_translation()
				#loc = bone.matrix * loc
				
				
				#loc += bone.loc
				 
				
				keyfram = Cal3DKeyFrame(time, loc, rot) 
				animation.tracks[bonename].keyframes[time]=(keyfram)
	
		for armachild in B_armature.children:	
			if armachild.type == 'ARMATURE':
				recursiveKeyframing(armachild, animation, time, AllArmatures)
		
		
def getBlenderArmatureAndBoneByBoneName(name):
	global ALLARMATURES
	for arm in ALLARMATURES.values():
		for b in arm.data.bones:
			if b.name==name:
				return [arm,b]
	return None
	
def getAllChildrens(cbone):
		ret=[]
		for c in cbone.children:
			ret.append(c)
			ret=ret+getAllChildren(c)
		return ret
			
#return list of bone names which are controlled by given bonename via a bone constraint
def getBonesDependingOn(bonename):
	from .Cal3DSkeleton import Cal3DSkeleton
	global ALLARMATURES
	
	ret=[]
	for arma in ALLARMATURES.values():
		for blendbone in arma.pose.bones:
			for cons in blendbone.constraints:
				try:
					#check dependant bone
					#if cons.type=='IK': #main bone constraint 
					#but enlarge crawling with all constraints that have subtarget bone ...possible errors introduced here but not with simple model
					if cons.type[0:6]!='LIMIT_':#limit rotation and limit translation seams to be main constraintes that have no subtarget attribute
						if cons.subtarget==bonename:
							#print("delegator found"+blendbone.name+"seams controlled by"+bonename)
							try:
								#cbone=Cal3DSkeleton.BONES[blendbone.name]
					
								#all parent bones are influenced by IK
								cbone=blendbone
								while cbone.parent:
									cbone= cbone.parent
									ret.append( cbone.name)
							except:print("")
													
							ret.append( blendbone.name)
							
							#recursive call (terminal case is reached when bonename is not a subtarget of any other bone)
							ret=ret+getBonesDependingOn(blendbone.name)
							
				except:print(cons.type+"havent a subtarget attribute") #case of cons.type[0:5]==LIMIT
				#TODO Check other artist bone constraint tricks like translationcopy , rotationcopy		
	return ret

#temporary type to store fcurves
class BlenderTransform:
	__slots__ = 'fscale','floc','fquat'
	def __init__():
		self.fscale=[]
		self.fpos=[]
		self.fquat=[]
		for i in range(3):
			self.floc.append(None)
		for i in range(3):
			self.fscale.append(None)
		for i in range(4):
			self.fquat.append(None)
			
	
	
def continuexport():
	global file_only_noext
	global skeleton
	global base_only
	global globfilename
	global blender_armature
	global selected
	global meshes 
	global blendmeshes
	global POSEBONES
	global KEYFRAMEARMATURES
	global KEYFRAMEDBONES
	global ALLARMATURES
	from .Cal3DMaterial import Cal3DMaterial
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	from .Cal3DMesh import Cal3DMesh
	from .Cal3DBlendShapeMesh import Cal3DBlendShapeMesh
	from .Cal3DSubMesh import Cal3DSubMesh
	from .Cal3DVertex import Cal3DVertex
	
	
	# ---- Export Mesh data ---------------------------------------------------
	from .Cal3DMaterial import Cal3DMaterial
	from .Cal3DBone import Cal3DBone
	from .Cal3DSkeleton import Cal3DSkeleton
	from .Cal3DMesh import Cal3DMesh
	from .Cal3DBlendShapeMesh import Cal3DBlendShapeMesh
		
	global skeleton
	global meshes 
	global blendmeshes
	meshes = []
	blendmeshes=[]
	#bpy.ops.object.mode_set(mode='OBJECT')
	#bpy.context.scene.frame_set(bpy.context.scene.frame_start);
	#Export Mesh a second time to take into acccount virtual armature changes
	print("Export Mesh a second time to take into acccount virtual armature changes")
	if EXPORTMESHES : exportMeshes(False)
	#purge useless bones
	
	print("purgeUseLessBones")
	skeleton.purgeUseLessBones()
	
	print("Export shape keys animation")
	MORPHANIMATIONS = []
	if EXPORTBLENDSHAPES:
		#parse Shape Key Motion curves TODO nomething more generic
		keyactions=[c for c in bpy.data.actions if c.name[0:3]=='Key' or c.name[0:6]=='Shapes']
		action_start = int( bpy.context.scene.frame_start ) 
		action_end = int( bpy.context.scene.frame_end ) 
		for keyaction in keyactions:
			anim=Cal3DMorphAnimation(keyaction.name,(action_end-action_start)/bpy.context.scene.render.fps)
			for curv in keyaction.fcurves:
			# assume rna is like key_blocks[" %name% "].value'
				blendshapename=curv.data_path[12:len(curv.data_path)-8]
				track=Cal3DMorphTrack(cleanJapaneseString(blendshapename))
				for pt in curv.keyframe_points:
					if pt.co.x < bpy.context.scene.frame_end and bpy.context.scene.frame_start<=pt.co.x: 
						track.keyframes.append(Cal3DMorphKeyFrame((pt.co.x-bpy.context.scene.frame_start)/bpy.context.scene.render.fps,pt.co.y))
				anim.tracks.append(track)
			
			MORPHANIMATIONS.append(anim)
	
	print("Export animation")
	#bpy.data.actions['KeyAction'].fcurves[0].keyframe_points[0].co
	# ---- Export animations --------------------------------------------------
	#backup_action = blender_armature.action
	if blender_armature:
		for arma in blender_armature:
			backup_action = arma.animation_data.action
		ANIMATIONS = []
		SUPPORTED_IPOS = 'QuatW', 'QuatX', 'QuatY', 'QuatZ', 'LocX', 'LocY', 'LocZ'
	
		#if PREF_ACT_ACTION_ONLY:
		if True:
			action_items = [(blender_armature[0].animation_data.action.name, blender_armature[0].animation_data.action)]
		#else:						action_items = Blender.Armature.NLA.GetActions().items()
	
		#print len(action_items), 'action_items'
		#for armachild in blender_armature.children:	
			#if armachild.type == 'ARMATURE':
				#action_items.append([(armachild.animation_data.action.name, armachild.animation_data.action)])
		for animation_name, blend_action in action_items:
		
			action_start = int( bpy.context.scene.frame_start ) # int( backup_action.frame_range[0] )
			action_end = int( bpy.context.scene.frame_end ) #int( backup_action.frame_range[1] )
   
		
			animation = Cal3DAnimation(animation_name)
		# ----------------------------
			ANIMATIONS.append(animation)
			animation.duration = 0.0

			if BAKEDEXPORT:
			# We need to set the action active if we are getting baked data
		#	pose_data = getBakedPoseData(blender_armature, action_start, action_end)
 			#pose = blender_armature.pose

   			#for bonename in blender_armature.data.bones.keys():
    			#posebonemat = mathutils.Matrix(pose.bones[bonename].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
				rangestart = int( bpy.context.scene.frame_start ) # int( arm_action.frame_range[0] )
				rangeend = int( bpy.context.scene.frame_end ) #int( arm_action.frame_range[1] )
				currenttime = rangestart 
				for arma in blender_armature:
					for bonename in arma.data.bones.keys():
						try:
							bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
						except:
							#print( "found a posebone animating a bone that is not part of the exported armature: " + bonename )
							continue
						animation.tracks[bonename] = Cal3DTrack(bone)
				# check children if they're armature too
				if CHILD_ARMATURE_TRY:
					for arma in blender_armature:
						for armachild in arma.children:	
							if armachild.type == 'ARMATURE':
								for bonename in armachild.data.bones.keys():
									try:
										bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
									except:
										print( "Track :found a posebone animating a bone that is not part of the exported armature: " + bonename )
										continue
									animation.tracks[bonename] = Cal3DTrack(bone)
				while currenttime <= rangeend: 
					bpy.context.scene.frame_set(currenttime)
					time = (currenttime - rangestart) / FPS #(assuming default 24fps for  anim)
					if time > animation.duration:
						animation.duration = time
						KEYFRAMEARMATURES = {}
						KEYFRAMEDBONES={}
					for arma in blender_armature:
						recursiveKeyframing(arma, animation, time,  ALLARMATURES.values())
					
					currenttime += 1


			# Fake, all we need is bone names
			#blend_action_ipos_items = [(pbone, True) for pbone in POSEBONES.iterkeys()]
			else:
				print("real  ipo pairs")
				delegatedbones={} #map memorizing influences of bones on others
				# bpy.data.actions.new('DUMMY')#create dummy action to store reconstructed fcurves
				#fcurves need to be reconstructed because of bone constraints
				#TODO create fcurve on tempSkeleton as it can't be created without object properties attached...:/
				#what the hell have they got in mind?!
				#For the moment use a custom inner linear keyframe interpolation : Cal3dTrack.evaluate(time)
				tempanimation = Cal3DAnimation('temporary')
				animation.duration=(bpy.context.scene.frame_end-bpy.context.scene.frame_start)/bpy.context.scene.render.fps
				for arma in ALLARMATURES.values():
			#for each armature
					if arma.animation_data.action:
						
						for icurv,curv in enumerate(arma.animation_data.action.fcurves):
							bone_name=curv.group.name
							#check all bones for aconstraint based on this bone
							delegates=delegatedbones[bone_name]=getBonesDependingOn(bone_name)
							if len(delegates)==0:delegates.append(bone_name)
							for bonename in delegates:
							#for each bone controlled by this bone	
							
							#	for arma in ALLARMATURES.values():
								#	for blendbone in arma.pose.bones:
							#			for cons in blendbone.constraints:
								#			if cons.type=='IK':
								#				#check dependant bone
								#				if cons.subtarget==bonename:
								#					#replace this ik bone by its target
								#					bonename=blendbone.name
								#					break
								
								try:
									bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
								except:
									#print( "found a posebone animating a bone that is not part of the exported armature: " + curv.group.name )
									 
									#exception :try to find IK_/FK_ prefix too
									#if bonename[1:3]=="K_" :
									#	bonename=bonename[3:len(bonename)]
										
									#try:
									#	bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
									#except:	
									#	continue
									#print(bonename)
									continue
								try:
									track  = animation.tracks[bonename]
								except:
									#first time create track
									animation.tracks[bonename] = Cal3DTrack(bone)
									track  = animation.tracks[bonename]
									tempanimation.tracks[bonename] = Cal3DTrack(bone)
								
								temptrack  = tempanimation.tracks[bonename]
								
									
									# create his fcurves too
									# for i in range(0,3):
										# dummycurve=D.actions['DUMMY'].fcurves.new(bonename+"_rotation")
										# dummycurve.array_index=i
										# myFCurves[bonename].frot[i]=dummycurves
									# for i in range(0,3):
										# dummycurve=D.actions['DUMMY'].fcurves.new(bonename+"_rotation")
										# dummycurve.array_index=i
									
									
								loc=mathutils.Vector((0,0,0))
								rot=mathutils.Quaternion((0,0,0,0))
								
								#create also keyframe with dummy member (except timecode) 
								for pt in curv.keyframe_points:
									if pt.co.x < bpy.context.scene.frame_end and bpy.context.scene.frame_start<=pt.co.x:
										track.keyframes[pt.co.x]=Cal3DKeyFrame((pt.co.x-bpy.context.scene.frame_start)/bpy.context.scene.render.fps,loc,rot)
										temptrack.keyframes[pt.co.x]=Cal3DKeyFrame((pt.co.x-bpy.context.scene.frame_start)/bpy.context.scene.render.fps,loc,rot)
									
										
						for icurv,curv in enumerate(arma.animation_data.action.fcurves):
							bone_name=curv.group.name
							#check all bones for a constraint based on this bone
							delegates=delegatedbones[bone_name]
							if len(delegates)==0:delegates.append(bone_name)
							for bonename in delegates:
								
								#replace this constraint bone by its target
								
								try:
									bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
								except:
									#print( "found a posebone animating a bone that is not part of the exported armature: " + curv.group.name )
									 
									#exception :try to find IK_/FK_ prefix too
									#if bonename[1:3]=="K_" :
									#	bonename=bonename[3:len(bonename)]
										
									#try:
									#	bone  = Cal3DSkeleton.BONES[bonename] #look up cal3d_bone
									#except:	
									#	continue
									#print(bonename)
									continue
								track  = animation.tracks[bonename]
								temptrack  = tempanimation.tracks[bonename]
								
								# try:
								     # t=curves[bonename]
								# except: 	 curves[bone_name]
								# if curv.data_path.find("scale")>0 :
											# scale=curv
										# else :
											# if curv.data_path.find("rotation")>0:
												# track.keyframes[pt.co.x].quat[curv.array_index]=curv
												
											# else:
												# if  curv.data_path.find("location")>0:
													# locs[bone_name].loc[curv.array_index]=curv
								for i,pt in enumerate( curv.keyframe_points):	
									if pt.co.x < bpy.context.scene.frame_end and bpy.context.scene.frame_start<=pt.co.x:
										#test rna name to know which channel semantic it represents
										
										if curv.data_path.find("scale")>0 :
											scale=pt.co.y
										else :
											if curv.data_path.find("rotation")>0:
												temptrack.keyframes[pt.co.x].quat[curv.array_index]=pt.co.y
												
											else:
												if  curv.data_path.find("location")>0:
													temptrack.keyframes[pt.co.x].loc[curv.array_index]=pt.co.y
											
				#last pass : do marmeladwith transforms
				
				
				bpy.context.scene.frame_set(bpy.context.scene.frame_start)
				for bone_name,track in tempanimation.tracks.items():
					bone=Cal3DSkeleton.BONES[bone_name]
					for time,keyp in track.keyframes.items():
						#print(str(time)+str(keyp))
						mat_trans = mathutils.Matrix.Translation(keyp.loc)
						mat_rot = mathutils.Quaternion(keyp.quat).to_matrix().to_4x4()
						
						
						posebonemat=mat_rot#keyp.quat.inverted().cross(bone.quat).to_matrix().to_4x4() #*mat_trans
						#posebonemat=mat_rot.inverted()*(bone.quat).to_matrix().to_4x4() #*mat_trans
						curbone=bone
						parentposemat=mathutils.Matrix()
						while curbone.cal3d_parent:
							parentposemat= tempanimation.tracks[curbone.cal3d_parent.name].evaluate(keyp.time)  * parentposemat
							curbone=curbone.cal3d_parent
						bonearma=getBlenderArmatureAndBoneByBoneName(bone.name)[0]
						parentposemat=bonearma.matrix_world*parentposemat
						parentposemat.invert()
						#posebonemat = parentposemat * posebonemat
							
						#HACK BAKE BONE TRANSFORM 	
						bpy.context.scene.frame_set(time)
						posebonemat=bonearma.pose.bones[bone.name].matrix.copy() 
						if bone.cal3d_parent:
							#get parent bone keyframe:
							
							
							#as we're not sure if bone.cal3d_parent as a key at time Have to bake parent transform
							#TODO retrieve parent's fcurves to avoid heavy frameset
							#bpy.context.scene.frame_set(time)
							
						
							armandboneparent=getBlenderArmatureAndBoneByBoneName(bone.cal3d_parent.name)
							
							if armandboneparent:
								#
								arma=armandboneparent[0]
								boneparent=armandboneparent[1]
															
								parentposemat = arma.pose.bones[bone.cal3d_parent.name].matrix.copy()  # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
								parentposemat.invert()
								posebonemat = parentposemat * posebonemat
									
							else:
								print(bone.cal3d_parent.name+"not found in armatures")
					
						else:
							posebonemat=bonearma.matrix_world *posebonemat
						loc = mathutils.Vector((posebonemat[3][0],
						posebonemat[3][1],
						posebonemat[3][2],
						))
						
						rot = posebonemat.to_quaternion() 
						rot.normalize() 
						loc=posebonemat.to_translation()
						#do not modify tempanimation as we use it in other iterations
						thegood=animation.tracks[bone_name].keyframes[time]
						thegood.loc=loc #+bone.loc
						thegood.quat=rot
					#track.keyframes=sorted(track.keyframes,key = lambda a: a)
						
			
	
	# Restore the original armature
	#blender_armature.action = backup_action
	# ------------------------------------- End Animation
	
	
	

	buff=('# Cal3D model exported from Blender \n')
	buff=('#Cal3dExporter addons created by J.Valentin\n')
	#if PREF_SCALE != 1.0:	buff+='scale=%.6f\n' % PREF_SCALE
	buff+='scale=%.6f\n' % SCALE 
	
	
	if WRITEBINARY:
		fname =  file_only_noext + '.csf'
		file = open( base_only +  fname, 'wb')
		skeleton.to_cal3d_binary(file)
	else:
		fname =  file_only_noext + '.xsf'
		file = open( base_only +  fname, 'wb')
		skeleton.writeCal3D(file)
	
	
	file.close()
	
	buff+=('skeleton=%s\n' % fname)
	
	if blender_armature:
		for animation in ANIMATIONS:
		
			if not animation.name.startswith('_'):
				if animation.duration > 0.1: # Cal3D does not support animation with only one state
					
					if WRITEBINARY:
						fname = new_name(file_only_noext,animation.name, '.caf')
						file = open(base_only + fname, 'wb')
						animation.to_cal3d_binary(file)
					else:
						fname = new_name(file_only_noext,animation.name, '.xaf')
						file = open(base_only + fname, 'wb')
						animation.writeCal3D(file)
					file.close()
					buff+=('animation=%s\n' % fname)
	for animation in MORPHANIMATIONS:
		if animation.duration > 0.1: # Cal3D does not support animation with only one state
					if WRITEBINARY and False:						
						fname = new_name(file_only_noext,animation.name, '.cpf')
						file = open(base_only + fname, 'wb')
						animation.to_cal3d_binary(file)
					else:
						fname = new_name(file_only_noext,animation.name, '.xpf')
						file = open(base_only + fname, 'wb')
						animation.writeCal3D(file)
					file.close()
					buff+=('morphanim=%s\n' % fname)
	if EXPORTMESHES :				
		for mesh in meshes:
			#print("mesh dur %s\n" %mesh.name)
			if not mesh.name.startswith('_'):
				if WRITEBINARY:	
					fname = new_name(file_only_noext,mesh.name, '.cmf')
					file = open(base_only + fname, 'wb')
					mesh.to_cal3d_binary(file)
				else:
					fname = new_name(file_only_noext,mesh.name, '.xmf')
					file = open(base_only + fname, 'wb')
					mesh.writeCal3D(file)
				file.close()
				
				buff+=('mesh=%s\n' % fname)

		#blendshape meshes	
		for blendmesh in blendmeshes:
			if not blendmesh.name.startswith('_'):
				if WRITEBINARY:	
					fname = new_name(file_only_noext,blendmesh.name, '.cmf')
					file = open(base_only + fname, 'wb')
					blendmesh.to_cal3d_binary(file)
				else:
					fname = new_name(file_only_noext,blendmesh.name, '.xmf')
					file = open(base_only + fname, 'wb')
					blendmesh.writeCal3D(file)

					file.close()
				buff+=('blendmesh=%s\n' % fname)

	materials = Cal3DMaterial.MATERIALS.values()
	MNames=[mname.id for mname in materials ]
	sortedmatkey=sorted(MNames)
	
	#.sort() #key = lambda a: a.id)
	for materialid in sortedmatkey:
		# Just number materials, its less trouble
		fname = new_name(file_only_noext,str(materialid), '.xrf')
		
		file = open(base_only + fname, 'wb')
		for k in materials :
			if k.id==materialid:
				material=k
		material.writeCal3D(file)
		file.close()
		
		buff+=('material=%s\n' % fname)
	
	#print 'Cal3D Saved to "%s.cfg"' % file_only_noext
	cfg = open((globfilename), 'wb')
	cfg.write(bytes(buff, 'UTF-8'));	
	cfg.close();
	POSEBONES= {}
	ALLARMATURES={}
	Cal3DSkeleton.BONES={}
	skeleton=None
	KEYFRAMEDBONES={}
	KEYFRAMEARMATURES={}
	print("end export")
	# Warnings
	

def export_cal3d_ui(filename):
	
	PREF_SCALE= Blender.Draw.Create(1.0)
	PREF_BAKE_MOTION = Blender.Draw.Create(1)
	PREF_ACT_ACTION_ONLY= Blender.Draw.Create(1)
	PREF_SCENE_FRAMES= Blender.Draw.Create(0)
	
	block = [\
	('Scale: ', PREF_SCALE, 0.01, 100, 'The scale to set in the Cal3d .cfg file (unsupported by soya)'),\
	('Baked Motion', PREF_BAKE_MOTION, 'use final pose position instead of ipo keyframes (IK and constraint support)'),\
	('Active Action', PREF_ACT_ACTION_ONLY, 'Only export action applied to this armature, else export all actions.'),\
	('Scene Frames', PREF_SCENE_FRAMES, 'Use scene frame range, else the actions start/end'),\
	]
	
	if not Blender.Draw.PupBlock('Cal3D Options', block):
		return
	
	Blender.Window.WaitCursor(1)
	export_cal3d(filename, 1.0/PREF_SCALE.val, PREF_BAKE_MOTION.val, PREF_ACT_ACTION_ONLY.val, PREF_SCENE_FRAMES.val)
	Blender.Window.WaitCursor(0)


#import os
if __name__ == '__main__':
	Blender.Window.FileSelector(export_cal3d_ui, 'Cal3D Export', Blender.Get('filename').replace('.blend', '.cfg'))
	#export_cal3d('/cally/data/skeleton/skeleton' + '.cfg', 1.0, True, False, False)
	#export_cal3d('/test' + '.cfg')
	#export_cal3d_ui('/test' + '.cfg')
	#os.system('cd /; wine /cal3d_miniviewer.exe /skeleton.cfg')
	#os.system('cd /cally/;wine cally')


 
##########
#export class registration and interface
from bpy.props import *
if DEBUGECLIPSE:
	PYDEV_SOURCE_DIR = 'D:\eclipse\plugins\org.python.pydev_3.0.0.201311051910\pysrc'
	PYDEV_SOURCE_DIR = '/home/pascal/.eclipse/org.eclipse.platform_3.8_155965261/plugins/org.python.pydev_3.1.0.201312121632/pysrc'
	import sys

	if sys.path.count(PYDEV_SOURCE_DIR) < 1:
	   sys.path.append(PYDEV_SOURCE_DIR)

	import pydevd

	pydevd.settrace()

	bling = "the parrot has ceased to be"
	print(bling)

#if sys.path.count(PYDEV_SOURCE_DIR) < 1:
#   sys.path.append(PYDEV_SOURCE_DIR)

#import pydevd

#pydevd.settrace()

#bling = "the parrot has ceased to be"
#print(bling)
class ExportCal3D(bpy.types.Operator):
	'''Export to Cal3d (.cfg)'''
	bl_idname = "export.cal3d"
	bl_label = 'Export CAL3D'
  
	ogenum = [("console","Console","log to console"),
             ("append","Append","append to log file"),
             ("overwrite","Overwrite","overwrite log file")]
             

	filepath = StringProperty(subtype = 'FILE_PATH',name="File Path", description="Filepath for exporting", maxlen= 1024, default= "")
	exportModes = [("mesh & anim", "Mesh & Anim", "Export .xmf and .xaf files."),
	 ("anim only", "Anim only.", "Export xsf and.xaf files."),
	 ("mesh only", "Mesh only.", "Export only.xmf ")]
	cal3DexportList = EnumProperty(name="Exports", items=exportModes, description="Choose export mode.", default='mesh & anim')

	
	PREFEXPORTBLENDSHAPES = BoolProperty(name="EXPORTBLENDSHAPES", description="EXPORTBLENDSHAPES",default=EXPORTBLENDSHAPES)
	PREFWRITEBINARY = BoolProperty(name="WRITEBINARY", description="WRITEBINARY",default=WRITEBINARY)
	PREFAPPLY_MODIFIERS = BoolProperty(name="APPLY_MODIFIERS", description="APPLY_MODIFIERS",default=APPLY_MODIFIERS)
	PREFBAKEDEXPORT= BoolProperty(name="BAKEDEXPORT", description="BAKEDEXPORT",default=BAKEDEXPORT)
	PREFINTERACTIVE_BONE_SELECTION= BoolProperty(name="INTERACTIVE_BONE_SELECTION", description="INTERACTIVE_BONE_SELECTION",default=INTERACTIVE_BONE_SELECTION)
	
	scale = FloatProperty(name="Scale", description="Scale all objects from world origin (0,0,0)",default=0.01,precision=5)
	fps = FloatProperty(name="FPS", description="animation sampling factor",default=24.0,precision=2)
	maxweightpervertex = IntProperty(name="max weight per vertex", description="maxweightpervertex",default=24)
	maxweight = FloatProperty(name="maxweight", description="maxweight",default=0.0,precision=5)
  
  
  
	def execute(self, context):
		#Update global parameters
		from .Cal3DVertex import Cal3DVertex
		global EXPORTBLENDSHAPES
		global WRITEBINARY
		global APPLY_MODIFIERS
		global BAKEDEXPORT
		global FPS
		global SCALE
		global EXPORTMESHES
		global INTERACTIVE_BONE_SELECTION
		print(self.properties.cal3DexportList)
		if self.properties.cal3DexportList=="anim only":
			EXPORTMESHES=False
		Cal3DVertex.MAXBONEPERMESH=self.properties.maxweightpervertex
		Cal3DVertex.WEIGHT_TRESHOLD=self.properties.maxweight
		FPS=self.properties.fps
		SCALE=self.properties.scale
		INTERACTIVE_BONE_SELECTION=self.properties.PREFINTERACTIVE_BONE_SELECTION
		EXPORTBLENDSHAPES = self.properties.PREFEXPORTBLENDSHAPES
		WRITEBINARY = self.properties.PREFWRITEBINARY
		APPLY_MODIFIERS = self.properties.PREFAPPLY_MODIFIERS
		BAKEDEXPORT = self.properties.PREFBAKEDEXPORT
		#launch export
		export_cal3d(self.properties.filepath)
		return {'FINISHED'}

	def invoke(self, context, event):
		WindowManager = context.window_manager
        # fixed for 2.56? Katsbits.com (via Nic B)
        # original WindowManager.add_fileselect(self)
		WindowManager.fileselect_add(self)
		return {"RUNNING_MODAL"}  


def menu_func(self, context):
	default_path = os.path.splitext(bpy.data.filepath)[0]
	self.layout.operator(ExportCal3D.bl_idname, text="Cal3d Model (.cfg)", icon='BLENDER').filepath = default_path
  
def register():
	bpy.utils.register_module(__name__)  #mikshaw
	bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
  bpy.utils.unregister_module(__name__)  #mikshaw
  bpy.types.INFO_MT_file_export.remove(menu_func)
  
# create a temporary rigged from collected bones info
def createEditableRig(name, origin, boneTable):
    # Create armature and object
	bpy.ops.object.add(
        type='ARMATURE', 
        enter_editmode=True,
        location=origin)
	ob = bpy.context.object
	ob.show_x_ray = True
	ob.name = name
	amt = ob.data
	amt.name = name+'Amt'
	amt.show_axes = True
 
	#check if tempBent is redundant
	if ob.name!=name:
		# print(ob.name+"name already exist")
		bpy.ops.object.delete()
		ob=[c for c in bpy.context.selectable_objects if c.name==name][0]
		ob.select=True
	else:
		# Create bones
		bpy.ops.object.mode_set(mode='EDIT')
		for (bname, pname, Cbone) in boneTable:  
			bone = amt.edit_bones.new(bname)
			bone.head = ob.matrix_world*Cbone.blendbone.matrix_local*Cbone.blendbone.head.copy()
			bone.tail = ob.matrix_world*Cbone.blendbone.matrix_local*Cbone.blendbone.tail.copy()
		for (bname, pname, Cbone) in boneTable:  
			bone = amt.edit_bones[bname]
			if pname:
				parent = amt.edit_bones[pname]
				bone.parent = parent
				bone.use_connect = True		
			
			#bone.tail = rot * mathutils.Vector(vector) + bone.head
		
		bpy.ops.object.mode_set(mode='OBJECT')
		ob.data.draw_type='STICK'
	return ob
 
def poseRig(ob, poseTable):
	bpy.context.scene.objects.active = ob
	bpy.ops.object.mode_set(mode='POSE')
	for (bname, axis, angle) in poseTable:
		pbone = ob.pose.bones[bname]
        # Set rotation mode to Euler XYZ, easier to understand
        # than default quaternions
		pbone.rotation_mode = 'XYZ'
        # Documentation bug: Euler.rotate(angle,axis):
        # axis in ['x','y','z'] and not ['X','Y','Z']
		pbone.rotation_euler.rotate_axis(axis, math.radians(angle))
	bpy.ops.object.mode_set(mode='OBJECT')

def watchBone(bone):
    #checkchildren for changes
	error=''
	ln=len(bone.name)-4
	bone_name=bone.name[0:ln]
	try: 
		
		Cbon=Cal3DSkeleton.BONES[bone_name]
				
	
	
		if bone.parent :
			ln=len(bone.parent.name)-4
			if bone.parent.name[0:ln]!=Cbon.cal3d_parent.name:
					temp=Cbon.cal3d_parent.name
					Cbon.cal3d_parent=Cal3DSkeleton.BONES[bone.parent.name[0:ln] ]	
					print("parent of  %s is changed from %s to %s \n" %(bone.name , temp ,Cbon.cal3d_parent.name))
	except:
		print('bone not found %s %s'%(bone.name[0:ln] ,bone.name))
		error='fok'
		#return;
	
	if error=='':
		for child in bone.children:
			if not watchBone( child):
				continue #TODO ERROR == REMOVE ALL CHILD
		return True;	
	else:return True
	
def watchBones(scene):
	from .Cal3DSkeleton import Cal3DSkeleton
	
	global skeleton
	
	#print("frame_change_pre:Check for bone parent cahnge in the temporary skeleton")
	#print("if so get Cal3d Bone model and update it")
	i=0
	SkeletonTemp=None
	try:
		#SkeletonTemp=scene.objects['Bent'].data
		SkeletonTemp=bpy.context.selected_objects[0].data
	except:
		i=0 
		return
	if bpy.context.selected_objects[0].name!='Bent':
		for a in bpy.app.handlers.scene_update_post :
			print(a.__name__)
			if a.__name__ == 'watchBones':
					bpy.app.handlers.scene_update_post.remove(a)
					continuexport()
		return			
		
		
	#override defective method in bender < 2.62
	try:
		for obj in bpy.context.selected_editable_bones:
			for c in obj.children:
				c.select=True
	except:
		i=0 #not critical eroor (none selected)
			
	if bpy.context.mode == 'OBJECT':
		for bone in SkeletonTemp.edit_bones: 
			watchBone(bone)
				
		#watch suppression TO DEBUG
		ret=False; #true if all are finded
		supp=None
		while not ret:
			bones=Cal3DSkeleton.BONES
			for bone in bones.values():
				
				ret=findinarmature(SkeletonTemp,bone.name+"temp");
				
				
				if ret :
					continue
				else:
					supp=bone
					break
			
			if not ret :
				
				skeleton.killBoneWithChildren(supp) 
				try:				
					#removeBoneFromSkelByName(supp)
					print("killBoneWithChildren%s\n"%supp.name)
					skeleton.rebuildBonesIndices()
					
				except:
					print("Error with removeBoneFromSkelByName %s\n"%supp.name)
					print(skeleton)
				
				try:				
					del Cal3DSkeleton.BONES[supp.name]
					print("removal from global BONES of bone%s\n"%supp)
				except:
					print("Error with global BONES removal of bone%s\n"%supp)
					#break
			else :
				break
		
			
			
def	findinarmature(arm,name)	:		
		for b in arm.bones:
				if findinbone(b,name): 
					return True;
		return False			
					
def findinbone(bone,name):
	if bone.name==name:return True;
	else:
		for i in bone.children:
			if findinbone(i,name):return True;
	return False;	
	
	
	
def buildtempSkeleton(origo,skeleton):
	
	origin = mathutils.Vector(origo)
    # Table of bones in the form (bone, parent, vector)
    # The vector is given in local coordinates
	boneTable1=[]
	for bone in skeleton.bones:
		#print(bone)
		if len(bone.children)>=0:
			#matrix=mathutils.Matrix.Translation(bone.translation_absolute-bone.cal3d_parent.translation_absolute)
			v=bone.tail-bone.head;
			#v=bone.children[0].quat.inverted().to_matrix()*(bone.loc)+bone.head;
			child=None
			if bone.cal3d_parent : child=bone.cal3d_parent.name +'temp'
			boneTable1.append((bone.name+'temp',child,bone))
			#print((bone.name+'temp',child,bone))
	
	
		
	
	#for c in bpy.context.selected_objects : c.select=False
	bpy.ops.object.select_all(action='DESELECT')
	#if  len(bpy.context.selected_objects )!=0:bpy.ops.object.select_all(action='DESELECT')
	tempsk =[c for c in bpy.context.selectable_objects if c.name=='Bent']
	if len(tempsk)>0 : #Bent already here so reuse it
		print("Bent already here so reuse it")
		#tempsk[0].select=True
		SkeletonTemp=tempsk[0]
		bpy.ops.object.select_all(action='DESELECT')
		bpy.ops.object.select_pattern(pattern='Bent')
	else:
		SkeletonTemp = createEditableRig('Bent', origin, boneTable1)
	#SkeletonTemp.select=True	
	
	
	
	bpy.ops.object.mode_set(mode='EDIT',toggle=True)
	bpy.app.handlers.scene_update_post.append(watchBones)
	
	

def point_distance(p1, p2):
  return math.sqrt((p2[0] - p1[0]) ** 2 + \
         (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)

class Spring:
  def __init__(self, vertex1, vertex2):
    self.vertex1 = vertex1
    self.vertex2 = vertex2
    self.spring_coefficient = 0.0
    self.idlelength = 0.0
    
  def to_cal3d(self):
    return struct.pack("iiff", self.vertex1.id, self.vertex2.id,
           self.spring_coefficient, self.idlelength)

  def to_cal3d_xml(self):
    return "    <SPRING VERTEXID=\"%i %i\" COEF=\"%f\" LENGTH=\"%f\"/>\n" % \
           (self.vertex1.id, self.vertex2.id, self.spring_coefficient,
           self.idlelength)

def generateSpringSystem(mesh): #,meshmodifier):
	
	oldstatus = 'STATUS'
	STATUS = "Calculating springsystem for cloth mesh"
	data=mesh.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
	

	springlist = []
	clonesprings = []
	clothmesh = data #.submeshes[0]

	faces = clothmesh.tessfaces

	# facemap is a list of all faces incident to this vertex
	# springs are placed between a vertex and all vertices of
	# the faces in facemap for that vertex

	# a blank map
	facemap = {}
	for v in clothmesh.vertices:
	   facemap[v.index] = []
	
	#fill up the mapmesh=C.selected_objects[0].to_mesh(C.scene,True,'PREVIEW')
	for i,f in enumerate(faces):
	   facemap[faces[i].vertices[0]].append(i)
	   facemap[faces[i].vertices[1]].append(i)
	   facemap[faces[i].vertices[2]].append(i)

	#now for each vertex we get the faces incident to it  
	for v in clothmesh.vertices:
		facelist = []
		vertlist = []
		for majface in facemap[v.index]:
		  # then for each vertex in the major faces we 
		  # get the faces incident to them
		  facelist = facelist +facemap[faces[majface].vertices[0]]
		  facelist = facelist + facemap [faces[majface].vertices[1]]
		  facelist = facelist + facemap [faces[majface].vertices[2]]
		
		#WARNING assume no duplicate 
		#elimdups(facelist)

		# and retrieve all the vertices in the faces
		for f in facelist:
		  vertlist.append(faces[f].vertices[0])
		  vertlist.append(faces[f].vertices[1])
		  vertlist.append(faces[f].vertices[2])

		#WARNING assume no duplicate
		#elimdup(vertlist)
		
		#now create springs between the vertices
		for sv in vertlist:
			springvert = clothmesh.vertices[sv]
			#dont put spring to self, or between anchor nodes
			if (not springvert.index == v.index):# and (\
                               #(not springvert.weight == 0.0):# \
                    			#or (  not v.weight == 0)):
				sp = [v.index, springvert.index]
				sp.sort()
				springlist.append(sp)
				#this should get cloned vertices to work.
				#requires a patch to cal3d0.9.1 for this to work
				#with no gaps appearing to the mesh
				#for c in springvert.clones:
					#sp = [springvert.index, c.index]
					#clonesprings.append(sp)
                  
            
                
			#for c in v.clones:
			  # sp = [v.id, c.id]
			   #clonesprings.append(sp)
			
	elimdups(springlist)
	#clonesprings = elimdup(clonesprings)
	springlist.sort()

	for sp in springlist:
	  spring = Spring(clothmesh.vertices[sp[0]], clothmesh.vertices[sp[1]])
	  isPin=False
	  for gr in clothmesh.vertices[sp[1]].groups:
	    if mesh.vertex_groups[gr.group].name[0:3]=="Pin":isPin=True
	  for gr in clothmesh.vertices[sp[0]].groups:
	    if mesh.vertex_groups[gr.group].name[0:3]=="Pin":isPin=True
	  if isPin:
            spring.spring_coefficient = 0
	  else:
            spring.spring_coefficient = 1000
	  spring.idlelength = point_distance(spring.vertex1.co, spring.vertex2.co)
	  #clothmesh.springs.append(spring)

	#for sp in clonesprings:
	  #spring = Spring(clothmesh.vertices[sp[0]], clothmesh.vertices[sp[1]])
	  #spring.spring_coefficient = 0
	  #spring.idlelength = 0.0
	  #clothmesh.springs.append(spring)

	#STATUS = oldstatus
	  
    
if __name__ == "__main__":
  register()
