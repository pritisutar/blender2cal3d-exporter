bl_info = { # changed from bl_addon_info in 2.57 -mikshaw
    "name": "Export Cal3d (.cfg)",
    "author": "MpEbUtCh3r et al",
    "version": (0,5,1),
    "blender": (2, 6, 2),
    "api": 31847,
    "location": "File > Export > Cal3d Skeletal Mesh/Animation Data (.cfg)",
    "description": "Export cal3d",
    "warning": "TODEBUG: bad meshes matrix dispatch the model in space\nTODO Features: Material Texture Files export, Collect IPO to avoid animation baking ",
    "wiki_url": "http://wiki.blender.org/",
    "tracker_url": "http://google.com",
    "category": "Import-Export"}	# changed from "Import/Export" -katsbits

# Enables LODs computation. LODs computation is quite slow, and the algo is
# surely not optimal :-(
LODS = 0

# Scale the model (not supported by Soya).

# See also BASE_MATRIX below, if you want to rotate/scale/translate the model at
# the exportation.

#########################################################################################
# Code starts here.
# The script should be quite re-useable for writing another Blender animation exporter.
# Most of the hell of it is to deal with Blender's head-tail-roll bone's definition.

import math
#import bpy

import bpy,struct,math,os,time,sys,mathutils

def best_armature_root(armature):
	#assume the first bone is the best hierarchy parent
	return armature.bones[0];
	
	bones = [bone for bone in armature.bones.values() if len(bone.children) >0 ]
	if len(bones) == 1:
		return bones[0]
	
	# Get the best root since we have more then 1
	bones = [(len(bone.children), bone) for bone in bones]

	bones.sort( key=lambda bone: bone[0])  ;
	#bones.sort()
	return bones[-1][1] # bone with most children




# Hack for having the model rotated right.
# Put in BASE_MATRIX your own rotation if you need some.

BASE_MATRIX = None


# Cal3D data structures

CAL3D_VERSION = 910
MATERIALS = {} # keys are (mat.name, img.name)


#problem with multiple texture material
class Cal3DMaterial(object):
	__slots__ = 'amb', 'diff', 'spec', 'shininess', 'maps_filenames', 'id'
	def __init__(self, blend_world, blend_material, blend_images):
		
		# Material Settings
		if blend_world:		amb = [ int(c*255) for c in blend_world.ambient_color ]
		else:				amb = [0,0,0] # Default value
		
		if blend_material:
			self.amb  = tuple([int(c*blend_material.ambient) for c in amb] + [255])
			self.diff = tuple([int(c*255) for c in blend_material.diffuse_color] + [int(blend_material.alpha*255)])
			self.spec = tuple([int(c*255) for c in blend_material.diffuse_color] + [int(blend_material.alpha*255)])
			self.shininess = (float(blend_material.specular_hardness)-1)/5.10
		else:
			self.amb  = tuple(amb + [255])
			self.diff = (255,255,255,255)
			self.spec = (255,255,255,255)
			self.shininess = 1.0
		
		self.maps_filenames = []
		#for image in blend_images:
			#if image:
				#print("image")
				#print(image) no multi tex for the moement
		if blend_images:self.maps_filenames.append( blend_images) #.split('\\')[-1].split('/')[-1] )
		print( blend_images)
		self.id = len(MATERIALS)
		MATERIALS[blend_material, blend_images] = self
	
	# new xml format
	def writeCal3D(self, file):
		buff='<?xml version="1.0"?>\n'
		buff+=('<HEADER MAGIC="XRF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<MATERIAL NUMMAPS="%s">\n' % len(self.maps_filenames))
		buff+=('\t<AMBIENT>%i %i %i %i</AMBIENT>\n' % self.amb)
		buff+=('\t<DIFFUSE>%i %i %i %i</DIFFUSE>\n' % self.diff)
		buff+=('\t<SPECULAR>%i %i %i %i</SPECULAR>\n' % self.spec)
		buff+=('\t<SHININESS>%.6f</SHININESS>\n' % self.shininess)
		
		for map_filename in self.maps_filenames:
			print(map_filename)
			buff+=('\t<MAP>%s</MAP>\n' % map_filename)
		
		buff+=('</MATERIAL>\n')
		file.write(bytes(buff, 'UTF-8'))

class Cal3DMesh(object):
	__slots__ = 'name', 'submeshes', 'matrix', 'matrix_normal'
	def __init__(self, ob, blend_mesh, blend_world):
		self.name      = ob.name
		self.submeshes = []
		
		#BPyMesh.meshCalcNormals(blend_mesh)
		blend_mesh.calc_normals()
		self.matrix = ob.matrix_world.copy()
		loc, rot, sca = self.matrix.copy().decompose()
		self.matrix_normal = rot.to_matrix() #mathutils.Matrix.Rotation(rot.angle, 4, rot.axis)
		
		#if BASE_MATRIX:
		#	matrix = matrix_multiply(BASE_MATRIX, matrix)
		
		face_groups = {}
		blend_materials = blend_mesh.materials
		uvlayers = ()
		mat = None # incase we have no materials
		print( len(blend_mesh.uv_textures))
		if len(blend_mesh.uv_textures)>0:
			uvlayers = blend_mesh.uv_textures
			if len(uvlayers) == 1:
				for f in blend_mesh.faces:
					image =	ob.data.materials[0].name	
								#(f.image,)  bit in a tuple so we can match multi UV code
					if blend_materials:	mat =	blend_materials[f.material_index] # if no materials, mat will always be None
					face_groups.setdefault( (mat,image), (mat,image,[]) )[2].append( f )
			else:
				# Multi UV's
				face_multi_images = [[] for i in range(len(blend_mesh.faces))]
				face_multi_uvs = [[[] for i in range(len(f))  ] for f in blend_mesh.faces]
				for uvlayer in uvlayers:
					blend_mesh.activeUVLayer = uvlayer
					for i, f in enumerate(blend_mesh.faces):
						face_multi_images[i].append(f.image)
						if f.image:
							for j, uv in enumerate(f.uv):
								face_multi_uvs[i][j].append( tuple(uv) )
				
				# Convert UV's to tuples so they can be compared with eachother
				# when creating new verts
				for fuv in face_multi_uvs:
					for i, uv in enumerate(fuv):
						fuv[i] = tuple(uv)
				
				for i, f in enumerate(blend_mesh.faces):
					image =						tuple(face_multi_images[i])
					if blend_materials: mat =	blend_materials[f.material_index]
					face_groups.setdefault( (mat,image), (mat,image,[]) )[2].append( f )
		else:
			# No UV's TODO:ADD VERTEX COLOR ELSE THE TINYXML CAL3DIMPORTER SHOULD FAIL LATTER WHEN USE IT:FOR THE MOMENT DONT EXPORT NO UV MESHES....
			for f in blend_mesh.faces:
				if blend_materials: mat =	blend_materials[f. material_index]
				face_groups.setdefault( (mat,()), (mat,(),[]) )[2].append( f )
		
		for blend_material, blend_images, faces in face_groups.values():
			print(blend_images)
			print("newmaterial")
			try:		material = MATERIALS[blend_material, blend_images]
			except:		material = MATERIALS[blend_material, blend_images] = Cal3DMaterial(blend_world, blend_material, blend_images)
			
			submesh = Cal3DSubMesh(self, material, len(self.submeshes))
			self.submeshes.append(submesh)
			
			# Check weather we need to write UVs, dont do it if theres no image
			# Multilayer UV's have alredy checked that they have images when 
			# building face_multi_uvs
			if len(uvlayers) == 1:
				if blend_images == (None,):
					write_single_layer_uvs = False
				else:
					write_single_layer_uvs = True
			
			
			for face in faces:
				
				
				
				face_vertices = []
				face_v = []
				for i in range(len(face.vertices)):
					face_v.append(blend_mesh.vertices[face.vertices[i]])		
				
				if not face.use_smooth:
					
					#normal = face_v[0].normal #pate
					p1 = blend_mesh.vertices[ face.vertices[0] ].co
					p2 = blend_mesh.vertices[ face.vertices[1] ].co
					p3 = blend_mesh.vertices[ face.vertices[2] ].co
					vv1 =  mathutils.Vector((p3[0] - p2[0], p3[1] - p2[1], p3[2] - p2[2]))
					vv2= mathutils.Vector((p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]))
					normal=vv1.cross(vv2)
              				#* w_matrix))
#uv = [blend_mesh.uv_textures.active.data[face.index].uv[i][0], blend_mesh.uv_textures.active.data[face.index].uv[i][1]]
				if len(uvlayers)>1:
					for i, blend_vert in enumerate(face_v):
						if face.use_smooth:		normal = blend_mesh.vertices[ face.vertices[i] ].normal
						
						vertex = submesh.getVertex(ob, blend_vert, normal, face_multi_uvs[face.index][i])
						face_vertices.append(vertex)
				
				elif len(uvlayers)==1:
				

					if write_single_layer_uvs:
						face_uv =[]#face.uv
						for i in range(len(face.vertices)):
							face_uv.append([blend_mesh.uv_textures.active.data[face.index].uv[i][0], blend_mesh.uv_textures.active.data[face.index].uv[i][1]])
					
					for i, blend_vert in enumerate(face_v):
						if face.use_smooth:		normal =blend_mesh.vertices[ face.vertices[i] ].normal
						
						if write_single_layer_uvs:	uvs = (tuple(face_uv[i]),)
						else:						uvs = ()
						
						vertex = submesh.getVertex(ob, blend_vert, normal, uvs )	
						face_vertices.append(vertex)
				else:
					# No UVs
					for i, blend_vert in enumerate(face_v):
						if face.use_smooth:		normal = blend_vert.normal
						vertex = submesh.getVertex(ob, blend_vert, normal, () )
						face_vertices.append(vertex)
				
				
				# Split faces with more than 3 vertices
				for i in range(1, len(face.vertices) - 1):
					submesh.faces.append(Cal3DFace(face_vertices[0], face_vertices[i], face_vertices[i + 1]))
	
	def writeCal3D(self, file):

		buff=('<?xml version="1.0"?>\n')
		buff+=('<HEADER MAGIC="XMF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<MESH NUMSUBMESH="%i">\n' % len(self.submeshes))
		for submesh in self.submeshes:
			buff+=submesh.writeCal3D(file, self.matrix, self.matrix_normal)
		buff+=('</MESH>\n')
		file.write(bytes(buff, 'UTF-8'));


class Cal3DSubMesh(object):
	__slots__ = 'material', 'vertices', 'vert_mapping', 'vert_count', 'faces', 'nb_lodsteps', 'springs', 'id'
	def __init__(self, mesh, material, id):
		self.material   = material
		self.vertices   = []
		self.vert_mapping = dict() # map original indicies to local
		self.vert_count = 0
		self.faces      = []
		self.nb_lodsteps = 0
		self.springs    = []
		self.id = id
	
	def getVertex(self, ob, blend_vert, normal, maps):
		'''
		Request a vertex, and create a new one or return a matching vertex
		'''
		blend_index = blend_vert.index
		con=False
		#print("index %d\n" %  blend_vert.index)
		#TypeError: unhashable type: 'list'
		keyz=self.vert_mapping.keys();
		for fok in keyz:
			if fok==blend_index:
				con=True
		if not con:
			influences = []	
			for j in range(len(ob.data.vertices[blend_index].groups )):
				inf = [ob.vertex_groups[ ob.data.vertices[ blend_index ].groups[j].group ].name, ob.data.vertices[blend_index].groups[j].weight]
				influences.append( inf )


			vertex = Cal3DVertex(blend_vert.co, normal, maps, influences)#blend_mesh.getVertexInfluences(blend_index))
			self.vertices.append([vertex])
			self.vert_mapping[blend_index] = len(self.vert_mapping)
			self.vert_count +=1
			return vertex
		else:
			index_map =self.vert_mapping[blend_index]
			vertex_list = self.vertices[index_map]
			
			for v in vertex_list:
				if	v.normal == normal and\
					v.maps == maps:
						return v # reusing
			
			# No match, add a new vert
			# Use the first verts influences
			vertex = Cal3DVertex(blend_vert.co, normal, maps, vertex_list[0].influences)
			vertex_list.append(vertex)
			# self.vert_mapping[blend_index] = len(self.vert_mapping)
			self.vert_count +=1
			return vertex
		
	
	def compute_lods(self):
		#'''Computes LODs info for Cal3D (there's no Blender related stuff here).'''
		
		#print "Start LODs computation..."
		vertex2faces = {}
		for face in self.faces:
			for vertex in (face.vertex1, face.vertex2, face.vertex3):
				l = vertex2faces.get(vertex)
				if not l: vertex2faces[vertex] = [face]
				else: l.append(face)
				
		couple_treated         = {}
		couple_collapse_factor = []
		for face in self.faces:
			for a, b in ((face.vertex1, face.vertex2), (face.vertex1, face.vertex3), (face.vertex2, face.vertex3)):
				a = a.cloned_from or a
				b = b.cloned_from or b
				if a.id > b.id: a, b = b, a
				if not couple_treated.has_key((a, b)):
					# The collapse factor is simply the distance between the 2 points :-(
					# This should be improved !!
					if vector_dotproduct(a.normal, b.normal) < 0.9: continue
					couple_collapse_factor.append((point_distance(a.loc, b.loc), a, b))
					couple_treated[a, b] = 1
			
		couple_collapse_factor.sort()
		
		collapsed    = {}
		new_vertices = []
		new_faces    = []
		for factor, v1, v2 in couple_collapse_factor:
			# Determines if v1 collapses to v2 or v2 to v1.
			# We choose to keep the vertex which is on the smaller number of faces, since
			# this one has more chance of being in an extrimity of the body.
			# Though heuristic, this rule yields very good results in practice.
			if   len(vertex2faces[v1]) <  len(vertex2faces[v2]): v2, v1 = v1, v2
			elif len(vertex2faces[v1]) == len(vertex2faces[v2]):
				if collapsed.get(v1, 0): v2, v1 = v1, v2 # v1 already collapsed, try v2
				
			if (not collapsed.get(v1, 0)) and (not collapsed.get(v2, 0)):
				collapsed[v1] = 1
				collapsed[v2] = 1
				
				# Check if v2 is already colapsed
				while v2.collapse_to: v2 = v2.collapse_to
				
				common_faces = filter(vertex2faces[v1].__contains__, vertex2faces[v2])
				
				v1.collapse_to         = v2
				v1.face_collapse_count = len(common_faces)
				
				for clone in v1.clones:
					# Find the clone of v2 that correspond to this clone of v1
					possibles = []
					for face in vertex2faces[clone]:
						possibles.append(face.vertex1)
						possibles.append(face.vertex2)
						possibles.append(face.vertex3)
					clone.collapse_to = v2
					for vertex in v2.clones:
						if vertex in possibles:
							clone.collapse_to = vertex
							break
						
					clone.face_collapse_count = 0
					new_vertices.append(clone)
	
				# HACK -- all faces get collapsed with v1 (and no faces are collapsed with v1's
				# clones). This is why we add v1 in new_vertices after v1's clones.
				# This hack has no other incidence that consuming a little few memory for the
				# extra faces if some v1's clone are collapsed but v1 is not.
				new_vertices.append(v1)
				
				self.nb_lodsteps += 1 + len(v1.clones)
				
				new_faces.extend(common_faces)
				for face in common_faces:
					face.can_collapse = 1
					
					# Updates vertex2faces
					vertex2faces[face.vertex1].remove(face)
					vertex2faces[face.vertex2].remove(face)
					vertex2faces[face.vertex3].remove(face)
				vertex2faces[v2].extend(vertex2faces[v1])
				
		new_vertices.extend(filter(lambda vertex: not vertex.collapse_to, self.vertices))
		new_vertices.reverse() # Cal3D want LODed vertices at the end
		for i in range(len(new_vertices)): new_vertices[i].id = i
		self.vertices = new_vertices
		
		new_faces.extend(filter(lambda face: not face.can_collapse, self.faces))
		new_faces.reverse() # Cal3D want LODed faces at the end
		self.faces = new_faces
		
		#print 'LODs computed : %s vertices can be removed (from a total of %s).' % (self.nb_lodsteps, len(self.vertices))
	
	
	def writeCal3D(self, file, matrix, matrix_normal):
		
		buff=('\t<SUBMESH NUMVERTICES="%i" NUMFACES="%i" MATERIAL="%i" ' % \
				(self.vert_count, len(self.faces), self.material.id))
		buff+=('NUMLODSTEPS="%i" NUMSPRINGS="%i" NUMTEXCOORDS="%i">\n' % \
				 (self.nb_lodsteps, len(self.springs),
				 len(self.material.maps_filenames)))
		
		i = 0
		for v in self.vertices:
			for item in v:
				item.id = i
				buff+=item.writeCal3D(file, matrix, matrix_normal)
				i += 1
		
		for item in self.springs:
			buff+=item.writeCal3D(file)
		for item in self.faces:
			buff+=item.writeCal3D(file)
		
		buff+=('\t</SUBMESH>\n')
		return buff;

class Cal3DVertex(object):
	__slots__ = 'loc','normal','collapse_to','face_collapse_count','maps','influences','weight','cloned_from','clones','id'
	def __init__(self, loc, normal, maps, blend_influences):
		self.loc    = mathutils.Vector(loc.copy())
		self.normal = mathutils.Vector(normal.copy())
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
				if BONES.get(bone_name):
					sum += weight
			
			for bone_name, weight in blend_influences:
				bone = BONES.get(bone_name)
				if not bone: # keys
					# print 'Couldnt find bone "%s" which influences object "%s"' % (bone_name, ob.name)
					continue
				
				if weight:
					self.influences.append(Cal3DInfluence(bone, weight / sum))
	
	
	def writeCal3D(self, file, matrix, matrix_normal):
		if self.collapse_to:
			collapse_id = self.collapse_to.id
		else:
			collapse_id = -1
		buff=('\t\t<VERTEX ID="%i" NUMINFLUENCES="%i">\n' % \
				(self.id, len(self.influences)))
		daloc=matrix*self.loc
		# Calculate global coords
		
		print(matrix)
		buff+=('\t\t\t<POS>%.6f %.6f %.6f</POS>\n' % (daloc[0],daloc[1],daloc[2]))
		
		danormal=matrix_normal*self.normal;
		danormal.normalize()
		#print(danormal)
		buff+=('\t\t\t<NORM>%.6f %.6f %.6f</NORM>\n' % tuple(danormal ))
		if collapse_id != -1:
			buff+=('\t\t\t<COLLAPSEID>%i</COLLAPSEID>\n' % collapse_id)
			buff+=('\t\t\t<COLLAPSECOUNT>%i</COLLAPSECOUNT>\n' % \
					 self.face_collapse_count)
		
		for uv in self.maps:
			# we cant have more UV's then our materials image maps
			# check for this
			buff+=('\t\t\t<TEXCOORD>%.6f %.6f</TEXCOORD>\n' % uv)
		
		for item in self.influences:
			buff+=item.writeCal3D(file)
		
		if self.weight != None:
			buff+=('\t\t\t<PHYSIQUE>%.6f</PHYSIQUE>\n' % len(self.weight))
		buff+=('\t\t</VERTEX>\n')
		return buff;

class Cal3DInfluence(object):
	__slots__ = 'bone', 'weight'
	def __init__(self, bone, weight):
		self.bone   = bone
		self.weight = weight
	
	def writeCal3D(self, file):
		return('\t\t\t<INFLUENCE ID="%i">%.6f</INFLUENCE>\n' % \
					 (self.bone.id, self.weight))

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

class Cal3DFace(object):
	__slots__ = 'vertex1', 'vertex2', 'vertex3', 'can_collapse',
	def __init__(self, vertex1, vertex2, vertex3):
		self.vertex1 = vertex1
		self.vertex2 = vertex2
		self.vertex3 = vertex3
		self.can_collapse = 0
	
	def writeCal3D(self, file):
		return('\t\t<FACE VERTEXID="%i %i %i"/>\n' % \
					 (self.vertex1.id, self.vertex2.id, self.vertex3.id))

class Cal3DSkeleton(object):
	__slots__ = 'bones'
	def __init__(self):
		self.bones = []
	
	def writeCal3D(self, file):
		buff=('<?xml version="1.0"?>\n')
		buff+=('<HEADER MAGIC="XSF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<SKELETON NUMBONES="%i">\n' % len(self.bones))
		for item in self.bones:
			buff+=item.writeCal3D(file)
		buff+=('</SKELETON>\n')
		file.write(bytes(buff, 'UTF-8'));

BONES = {}
POSEBONES= {}
class Cal3DBone(object):
	__slots__ = 'translation_absolute','rotation_absolute','head', 'tail', 'name', 'cal3d_parent', 'loc','child_loc', 'quat', 'children', 'matrix', 'lloc', 'lquat', 'id'
	def __init__(self, skeleton, blend_bone, arm_matrix, cal3d_parent=None):
		
		# head tail of the bone relative to parent
		#head = arm_matrix*mathutils.Vector(blend_bone.head_local)
		#tail = arm_matrix*mathutils.Vector(blend_bone.tail_local)
		
		#print parent.quat
		# Turns the Blender's head-tail-roll notation into a quaternion
		#quat = matrix2quaternion(blender_bone2matrix(head, tail, blend_bone.roll['BONESPACE']))
		bonespace=blend_bone.matrix.copy()
		#mymatislocal
		head = blend_bone.head.copy()
		tail = blend_bone.tail.copy()
		#if cal3d_parent:bonespace=cal3d_parent.quat.to_matrix()*blend_bone.matrix;
		quat =bonespace.to_quaternion()
				
		self.child_loc=tail-head
		#quat =  matrix2quaternion(mymat)
		#if quat.w<0: quat.x=quat.x*-1.0;quat.y=quat.y*-1.0;quat.z=quat.z*-1.0 ;quat.w=quat.w*-1.0
		# Pose location
		 #ploc = POSEBONES[blend_bone.name].loc
		
		if cal3d_parent:
            # Compute the translation from the parent bone's head to the child
            # bone's head, in the parent bone coordinate system.
            # The translation is parent_tail - parent_head + child_head,
            # but parent_tail and parent_head must be converted from the parent's parent
            # system coordinate into the parent system coordinate.
			mymat= cal3d_parent.quat.to_matrix() #blend_bone.parent.matrix.copy();
			mymat.invert();
			parent_head=mymat*cal3d_parent.head
			
			parent_tail=mymat*cal3d_parent.tail
			
			#mymat=blend_bone.matrix_local*blend_bone.parent.matrix_local.inverted();
			#loc=mathutils.Vector((mymat[3][0],mymat[3][1],mymat[3][2]))
		
		
			#quat=mymat.to_quaternion();
			
			
			#mymat2=mymat*quat.to_matrix().to_4x4();
			#quat is global rotation
			#quat = mymat2.to_quaternion();
            #parent_head = vector_by_matrix_3x3(cal3d_parent.head, parent_invert_transform)
            #parent_tail = vector_by_matrix_3x3(cal3d_parent.tail, parent_invert_transform)
			#ploc = ploc+ mathutils.Vector(blend_bone.head)
           
            # EDIT!!! FIX BONE OFFSET BE CAREFULL OF THIS PART!!! ??
            #diff = vector_by_matrix_3x3(head, parent_invert_transform)
			parent_tail=parent_tail+ head # vector_add(parent_tail, head)
            # DONE!!!
           
			parentheadtotail = parent_tail-parent_head #vector_sub(parent_tail, parent_head)
            # hmm this should be handled by the IPos, but isn't for non-animated
            # bones which are transformed in the pose mode...
			loc=parentheadtotail; #mathutils.Vector(blend_bone.tail-blend_bone.head)
			#loc.rotate(cal3d_parent.quat.inverted())
			#loc = cal3d_parent.child_loc.copy()
			#loc.rotate(cal3d_parent.quat.inverted())
		else:
            # Apply the armature's matrix to the root bones
			head = arm_matrix*head #point_by_matrix(head, arm_matrix)
			tail = arm_matrix*tail
			#tail = point_by_matrix(tail, arm_matrix)
           
			loc = head
		
			mymat2=bonespace.to_4x4().copy()
			mymat2=arm_matrix*mymat2;
			#quat is global rotation
			quat = mymat2.to_quaternion();
			#quat = matrix2quaternion(matrix_multiply(arm_matrix, quaternion2matrix(quat))) # Probably not optimal
			
		self.head = head
		self.tail = tail
		
		self.cal3d_parent = cal3d_parent
		self.name   = blend_bone.name
		self.loc = loc
		self.quat = quat
		self.children = []
		self.matrix=quat.to_matrix().to_4x4().copy();
		#self.matrix = matrix_translate(quaternion2matrix(quat), loc)
		self.matrix[3][0] += loc[0]
		self.matrix[3][1] += loc[1]
		self.matrix[3][2] += loc[2]
		
		#self.matrix=mathutils.Matrix(arm_matrix) * mathutils.Matrix( blend_bone.matrix_local) global transorm
		
		if cal3d_parent:
			self.matrix = cal3d_parent.matrix*self.matrix
		#self.matrix = mathutils.Matrix(arm_matrix) * mathutils.Matrix(blend_bone.matrix_local) 
		# lloc and lquat are the bone => model space transformation (translation and rotation).
		# They are probably specific to Cal3D.
		#mymat2 = matrix_invert(self.matrix.copy()
		mymat2=self.matrix.inverted()
		
		self.lloc =mathutils.Vector((mymat2[3][0], mymat2[3][1], mymat2[3][2]))
		
		self.lquat = mymat2.to_quaternion();
		
		# Cal3d does the vertex deform calculation by:
		#   translationBoneSpace = coreBoneTranslationBoneSpace * boneAbsRotInAnimPose + boneAbsPosInAnimPose
		#   transformMatrix = coreBoneRotBoneSpace * boneAbsRotInAnimPose
		#   v = mesh * transformMatrix + translationBoneSpace
		# To calculate "coreBoneTranslationBoneSpace" (ltrans) and "coreBoneRotBoneSpace" (lquat)
		# we invert the absolute rotation and translation.
		
		
		
		self.id = len(skeleton.bones)
		skeleton.bones.append(self)
		BONES[self.name] = self
		
		if len(blend_bone.children)<1 :	return
		for blend_child in blend_bone.children:
			self.children.append(Cal3DBone(skeleton, blend_child, arm_matrix, self))
		

	def writeCal3D(self, file):
		buff=('\t<BONE ID="%i" NAME="%s" NUMCHILD="%i">\n' % \
				(self.id, self.name, len(self.children)))
		# We need to negate quaternion W value, but why ?
		buff+=('\t\t<TRANSLATION>%.6f %.6f %.6f</TRANSLATION>\n' % \
				 (self.loc[0], self.loc[1], self.loc[2]))
		if True:
			buff+=('\t\t<ROTATION>%.6f %.6f %.6f %.6f</ROTATION>\n' % \
				 (self.quat.x, self.quat.y, self.quat.z, -self.quat.w))
		else:
			buff+=('\t\t<ROTATION>%.6f %.6f %.6f %.6f</ROTATION>\n' % \
				 (-self.quat[0], -self.quat[1], -self.quat[2], -self.quat[3]))
		buff+=('\t\t<LOCALTRANSLATION>%.6f %.6f %.6f</LOCALTRANSLATION>\n' % \
				 (self.lloc[0], self.lloc[1], self.lloc[2]))
		if  True:
			buff+=('\t\t<LOCALROTATION>%.6f %.6f %.6f %.6f</LOCALROTATION>\n' % \
				 (self.lquat.x, self.lquat.y, self.lquat.z, -self.lquat.w))
		else:
			buff+=('\t\t<LOCALROTATION>%.6f %.6f %.6f %.6f</LOCALROTATION>\n' % \
				 (-self.lquat[0], -self.lquat[1], -self.lquat[2], -self.lquat[3]))
		if self.cal3d_parent:
			buff+=('\t\t<PARENTID>%i</PARENTID>\n' % self.cal3d_parent.id)
		else:
			buff+=('\t\t<PARENTID>%i</PARENTID>\n' % -1)
		
		for item in self.children:
			buff+=('\t\t<CHILDID>%i</CHILDID>\n' % item.id)
			
		buff+=('\t</BONE>\n')
		return buff

class Cal3DAnimation:
	def __init__(self, name, duration = 0.0):
		self.name     = name
		self.duration = duration
		self.tracks   = {} # Map bone names to tracks
	
	def writeCal3D(self, file):
		buff=('<?xml version="1.0"?>\n')
		buff+=('<HEADER MAGIC="XAF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<ANIMATION DURATION="%.6f" NUMTRACKS="%i">\n' % \
				 (self.duration, len(self.tracks)))
		
		for item in self.tracks.values():
			buff+=item.writeCal3D(file)
		buff+=('</ANIMATION>\n')
		file.write(bytes(buff, 'UTF-8'))

class Cal3DTrack(object):
	__slots__ = 'bone', 'keyframes'
	def __init__(self, bone):
		self.bone      = bone
		self.keyframes = []

	def writeCal3D(self, file):
		buff=('\t<TRACK BONEID="%i" NUMKEYFRAMES="%i">\n' %
				(self.bone.id, len(self.keyframes)))
		for item in self.keyframes:
			buff+=item.writeCal3D(file)
		buff+=('\t</TRACK>\n')
		return buff;

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


def getObjectArmature(ob):
	'''
	This returns the first armature the mesh uses.
	remember there can be more then 1 armature but most people dont do that.
	'''
	if ob.type != 'Mesh':
		return None
	
	arm = ob.parent
	if arm and arm.type == 'ARMATURE' and ob.parentType == Blender.Object.ParentTypes.ARMATURE:
		arm
	
	for m in ob.modifiers:
		if m.type== Blender.Modifier.Types.ARMATURE:
			arm = m[Blender.Modifier.Settings.OBJECT]
			if arm:
				return arm
	
	return None

def getBakedPoseData(ob_arm, start_frame, end_frame, ACTION_BAKE = False, ACTION_BAKE_FIRST_FRAME = True):
	'''
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
	ob_arm.action = backup_action
	if ACTION_BAKE==False:
		#Blender.Set('curframe', backup_frame)
		return bake_data
	elif ACTION_BAKE==True:
		return new_action
	#else: print "ERROR: Invalid ACTION_BAKE %i sent to BPyArmature" % ACTION_BAKE

	



def export_cal3d(filename, PREF_SCALE=0.1, PREF_BAKE_MOTION = True, PREF_ACT_ACTION_ONLY=True, PREF_SCENE_FRAMES=False):
	bpy.context.scene.frame_set(bpy.context.scene.frame_start);
	bpy.ops.object.mode_set(mode='OBJECT')
	sce =bpy.context.scene;
	if not filename.endswith('.cfg'):
		filename += '.cfg'
	
	file_only = filename.split('/')[-1].split('\\')[-1]
	file_only_noext = file_only.split('.')[0]
	base_only = filename[:-len(file_only)]
	
	def new_name(dataname, ext):
		#return file_only_noext + '_' + BPySys.cleanName(dataname) + ext
		return file_only_noext + '_' + dataname + ext
	#if EXPORT_FOR_SOYA:
	#	global BASE_MATRIX
	#	BASE_MATRIX = matrix_rotate_x(-math.pi / 2.0)
	# Get the sce

	# bpy.data.scenes.active
	blend_world = sce.world
	# ---- Export skeleton (armature) ----------------------------------------
	
	skeleton = Cal3DSkeleton()


	blender_armature = [ob for ob in bpy.context.selected_objects if ob.type == 'ARMATURE']
	#if len(blender_armature) > 1:	print "Found multiple armatures! using ",armatures[0].name
	if blender_armature: blender_armature = blender_armature[0]
	else:
		# Try find a meshes armature
		for ob in bpy.context.selected_objects:
			blender_armature = getObjectArmature(ob)
			if blender_armature:
				break
		
		if not blender_armature:
			print('Aborting%t|No Armature in selection only export meshes and texture youwill have to merge the two differtents.cfg mannually')
			#return

	# we need pose bone locations
		
	for pbone in blender_armature.data.bones.values():
			POSEBONES[pbone.name] = pbone
	for masterbone in blender_armature.data.bones:
		if not masterbone.parent:
			#if blender_armature:Cal3DBone(skeleton, best_armature_root(blender_armature.data), blender_armature.matrix_world)
			Cal3DBone(skeleton, masterbone, blender_armature.matrix_world)
			
	# ---- Export Mesh data ---------------------------------------------------
	meshes = []
	for ob in  bpy.context.selected_objects:
		print( "Processing mesh: "+ ob.name+ ob.type )
		if ob.type != 'MESH':continue
		print("mesh found in selection")
		#blend_mesh = ob.getData(mesh=1)
		
		if not ob.data.faces:			continue
		meshes.append( Cal3DMesh(ob, ob.data, blend_world) )
	
	# ---- Export animations --------------------------------------------------
	#backup_action = blender_armature.action
	if blender_armature:
		backup_action = blender_armature.animation_data.action
		ANIMATIONS = []
		SUPPORTED_IPOS = 'QuatW', 'QuatX', 'QuatY', 'QuatZ', 'LocX', 'LocY', 'LocZ'
	
		if PREF_ACT_ACTION_ONLY:	action_items = [(blender_armature.animation_data.action.name, blender_armature.animation_data.action)]
		else:						action_items = Blender.Armature.NLA.GetActions().items()
	
		#print len(action_items), 'action_items'
	
		for animation_name, blend_action in action_items:
		
		# get frame range
			if PREF_SCENE_FRAMES:
				action_start=	Blender.Get('staframe')
				action_end=		Blender.Get('endframe')
			else:
				action_start = int( bpy.context.scene.frame_start ) # int( backup_action.frame_range[0] )
				action_end = int( bpy.context.scene.frame_end ) #int( backup_action.frame_range[1] )
   
			#_frames = blend_action.getFrameNumbers()
			#action_start=	min(_frames);
			#action_end=		max(_frames);
			#del _frames
		
		#blender_armature.action = blend_action
			blender_armature.animation_data.action = blend_action
			animation = Cal3DAnimation(animation_name)
		# ----------------------------
			ANIMATIONS.append(animation)
			animation.duration = 0.0

			if PREF_BAKE_MOTION:
			# We need to set the action active if we are getting baked data
		#	pose_data = getBakedPoseData(blender_armature, action_start, action_end)
 			#pose = blender_armature.pose

   			#for bonename in blender_armature.data.bones.keys():
    			#posebonemat = mathutils.Matrix(pose.bones[bonename].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
				rangestart = int( bpy.context.scene.frame_start ) # int( arm_action.frame_range[0] )
				rangeend = int( bpy.context.scene.frame_end ) #int( arm_action.frame_range[1] )
				currenttime = rangestart

				for bonename in blender_armature.data.bones.keys():
					try:
						bone  = BONES[bonename] #look up cal3d_bone
					except:
						#print( "found a posebone animating a bone that is not part of the exported armature: " + bonename )
						continue
					animation.tracks[bonename] = Cal3DTrack(bone)

				while currenttime <= rangeend: 
					bpy.context.scene.frame_set(currenttime)
					time = (currenttime - rangestart) / 24.0 #(assuming default 24fps for  anim)
					if time > animation.duration:
						animation.duration = time
					pose = blender_armature.pose

					for bonename in blender_armature.data.bones.keys():
					
						try:
							bone  = BONES[bonename] #look up cal3d_bone
						except:
							print( "found a posebone animating a bone that is not part of the exported armature: " + bonename )
							continue
						posebonemat = mathutils.Matrix(pose.bones[bonename].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
						
						if bone.cal3d_parent:
						# need parentspace-matrix
							parentposemat = mathutils.Matrix(pose.bones[bone.cal3d_parent.name].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
#          posebonemat = parentposemat.invert() * posebonemat #reverse order of multiplication!!!
							parentposemat.invert()
							posebonemat = parentposemat * posebonemat 
						else:
							posebonemat=blender_armature.matrix_world*posebonemat
					#reverse order of multiplication!!!
						loc = mathutils.Vector((posebonemat[3][0],
						posebonemat[3][1],
						posebonemat[3][2],
						))
					#rot=posebonemat.to_quat().normalize()
						rot = posebonemat.to_quaternion() 
					#changed from to_quat in 2.57 -mikshaw
						rot.normalize() 
						
						posebonemat = mathutils.Matrix(pose.bones[bonename].matrix )
						loc = mathutils.Vector((posebonemat[3][0],
						posebonemat[3][1],
						posebonemat[3][2],
						))
						quat=posebonemat.to_quaternion()
						loc=bone.matrix*loc
						loc+=bone.loc
						quat*=bone.quat
						
					
						quat.normalize()
						
						#rot = [rot.w,rot.x,rot.y,rot.z]
#animation.addkeyforbone(bone.id, time, loc, rot)
						#rot = tuple(rot)
						#print("keyfram at %f\n" %time)
						keyfram=Cal3DKeyFrame(time, loc, rot) 
						animation.tracks[bonename].keyframes.append( keyfram )
						#print("%d\n"%len(animation.tracks[bonename].keyframes))
					currenttime += 1


			# Fake, all we need is bone names
			#blend_action_ipos_items = [(pbone, True) for pbone in POSEBONES.iterkeys()]
			else:
			#.... real (bone_name, ipo) pairs
				
				blend_action_ipos_items = blend_action.getAllChannelIpos().items()
		
			# Now we mau have some bones with no channels, easiest to add their names and an empty list here
			# this way they are exported with dummy keyfraames at teh first used frame
				action_bone_names = [name for name, ipo in blend_action_ipos_items]
				for bone_name in BONES: # iterkeys
					if bone_name not in action_bone_names:
						blend_action_ipos_items.append( (bone_name, []) )
		
		
			if False:
#		for bone_name, ipo in blend_action_ipos_items:
			# Baked bones may have no IPO's width motion still
#			if bone_name not in BONES:
			#	print '\tNo Bone "' + bone_name + '" in (from Animation "' + animation_name + '") ?!?'
#				continue
			
			# So we can loop without errors
#			if ipo==None: ipo = [] 
#			
#			bone = BONES[bone_name]
#			track = animation.tracks[bone_name] = Cal3DTrack(bone)
			
				if PREF_BAKE_MOTION:
					for i in xrange(action_end-action_end):
#action_end - action_start):
						cal3dtime = i / 25.0 # assume 25FPS by default
					
						if cal3dtime > animation.duration:
							animation.duration = cal3dtime
					
					#print pose_data[i][bone_name], i
						loc, quat = pose_data[i][bone_name]
					
						loc = vector_by_matrix_3x3(loc, bone.matrix)
						loc = vector_add(bone.loc, loc)
						quat = quaternion_multiply(quat, bone.quat)
						quat = mathutils.Quaternion(quat)
					
						quat.normalize()
						#quat = tuple(quat)
					
						track.keyframes.append( Cal3DKeyFrame(cal3dtime, loc, quat) )
			
				else:
				#run 1: we need to find all time values where we need to produce keyframes
					times = set()
					for curve in ipo:
						curve_name = curve.name
						if curve_name in SUPPORTED_IPOS:
							for p in curve.bezierPoints:
								times.add( p.pt[0] )
				
					times = list(times)
					times.sort()
				
				# Incase we have no keys here or ipo==None
					if not times: times.append(action_start)

				# run2: now create keyframes
					for time in times:
						cal3dtime = (time-1) / 25.0 # assume 25FPS by default
						if cal3dtime > animation.duration:
							animation.duration = cal3dtime
					
						trans = mathutils.Vector()
						quat  = mathutils.Quaternion()
					
						for curve in ipo:
							val = curve.evaluate(time)
						# val = 0.0 
							curve_name= curve.name
							if   curve_name == 'LocX':  trans[0] = val
							elif curve_name == 'LocY':  trans[1] = val
							elif curve_name == 'LocZ':  trans[2] = val
							elif curve_name == 'QuatW': quat.w = val
							elif curve_name == 'QuatX': quat.x  = val
							elif curve_name == 'QuatY': quat.y  = val
							elif curve_name == 'QuatZ': quat.z  = val
					
						transt = vector_by_matrix_3x3(trans, bone.matrix)
						loc = vector_add(bone.loc, transt)
						quat = quaternion_multiply(quat, bone.quat)
						quat = mathutils.Quaternion(quat)
					
						quat.normalize()
						quat = tuple(quat)
					
						track.keyframes.append( Cal3DKeyFrame(cal3dtime, loc, quat) )
		
		
			if animation.duration <= 0:
			#print 'Ignoring Animation "' + animation_name + '": duration is 0.\n'
				continue
	
	# Restore the original armature
	#blender_armature.action = backup_action
	# ------------------------------------- End Animation
	
	
	

	buff=('# Cal3D model exported from Blender with export_cal3d.py\n# from \n')
	
	if PREF_SCALE != 1.0:	buff+='scale=%.6f\n' % PREF_SCALE
	
	fname = file_only_noext + '.xsf'
	file = open( base_only +  fname, 'wb')
	skeleton.writeCal3D(file)
	file.close()
	
	buff+=('skeleton=%s\n' % fname)
	
	if blender_armature:
		for animation in ANIMATIONS:
		
			if not animation.name.startswith('_'):
				if animation.duration > 0.1: # Cal3D does not support animation with only one state
					fname = new_name(animation.name, '.xaf')
					file = open(base_only + fname, 'wb')
					animation.writeCal3D(file)
					file.close()
					buff+=('animation=%s\n' % fname)
	
	for mesh in meshes:
		print("mesh dur %s\n" %mesh.name)
		if not mesh.name.startswith('_'):
			fname = new_name(mesh.name, '.xmf')
			file = open(base_only + fname, 'wb')
			mesh.writeCal3D(file)
			file.close()
			
			buff+=('mesh=%s\n' % fname)
	
	materials = MATERIALS.values()
	#old materials.sort(key = lambda a: a.id)
	for material in materials:
		# Just number materials, its less trouble
		fname = new_name(str(material.id), '.xrf')
		
		file = open(base_only + fname, 'wb')
		material.writeCal3D(file)
		file.close()
		
		buff+=('material=%s\n' % fname)
	
	#print 'Cal3D Saved to "%s.cfg"' % file_only_noext
	cfg = open((filename), 'wb')
	cfg.write(bytes(buff, 'UTF-8'));	
	cfg.close();
	# Warnings
	if blender_armature:
		if len(animation.tracks) < 2:
			Blender.Draw.PupMenu('Warning, the armature has less then 2 tracks, file may not load in Cal3d')


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
class ExportCal3D(bpy.types.Operator):
  '''Export to Cal3d (.cfg)'''
  bl_idname = "export.cal3d"
  bl_label = 'Export CAL3D'
  
  logenum = [("console","Console","log to console"),
             ("append","Append","append to log file"),
             ("overwrite","Overwrite","overwrite log file")]
             
  #search for list of actions to export as .md5anims
  #md5animtargets = []
  #for anim in bpy.data.actions:
  #	md5animtargets.append( (anim.name, anim.name, anim.name) )
  	
  #md5animtarget = None
  #if( len( md5animtargets ) > 0 ):
  #	md5animtarget = EnumProperty( name="Anim", items = md5animtargets, description = "choose animation to export", default = md5animtargets[0] )
  	
  exportModes = [("mesh & anim", "Mesh & Anim", "Export .md5mesh and .md5anim files."),
  		 ("anim only", "Anim only.", "Export .md5anim only."),
  		 ("mesh only", "Mesh only.", "Export .md5mesh only.")]

  filepath = StringProperty(subtype = 'FILE_PATH',name="File Path", description="Filepath for exporting", maxlen= 1024, default= "")
  md5name = StringProperty(name="MD5 Name", description="MD3 header name / skin path (64 bytes)",maxlen=64,default="")
  md5exportList = EnumProperty(name="Exports", items=exportModes, description="Choose export mode.", default='mesh & anim')
  #md5logtype = EnumProperty(name="Save log", items=logenum, description="File logging options",default = 'console')
  md5scale = FloatProperty(name="Scale", description="Scale all objects from world origin (0,0,0)",default=1.0,precision=5)
  #md5offsetx = FloatProperty(name="Offset X", description="Transition scene along x axis",default=0.0,precision=5)
  #md5offsety = FloatProperty(name="Offset Y", description="Transition scene along y axis",default=0.0,precision=5)
  #md5offsetz = FloatProperty(name="Offset Z", description="Transition scene along z axis",default=0.0,precision=5)
  
  

  def execute(self, context):
# settings = md5Settings(savepath = self.properties.filepath,
                 #         scale = self.properties.md5scale,
                   #       exportMode = self.properties.md5exportList
                    #      )
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

if __name__ == "__main__":
  register()
