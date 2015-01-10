CAL3D_VERSION = 910

#shapekeycpt=0
#blend_mesh.active_shape_key_index=shapekeycpt
#current_shapekey=blend_mesh.active_shape_key
##For each shapekeys reset value
#while current_shapekey!=None:

	## assume first shape key is the base so go to next shape key
	#shapekeycpt=shapekeycpt+1
	#blend_mesh.active_shape_key_index=shapekeycpt
	#current_shapekey=blend_mesh.active_shape_key
	
	#reset blendshape
	#current_shapekey.value=0

#now setshape to 1 then export
#shapekeycpt=0
#while current_shapekey!=None:

	## assume first shape key is the base so go to next shape key
	#shapekeycpt=shapekeycpt+1
	#blend_mesh.active_shape_key_index=shapekeycpt
	#current_shapekey=blend_mesh.active_shape_key
	
	#activate blendshape
	#current_shapekey.value=1
	
	#current_shapekey.value=0
	##now export mesh
	##DEBUG: Export as obj
	#mesh=blend_mesh.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE)
	
APPLY_MODIFIERS=True
MESH_EXPORT_MODE='PREVIEW' #'RENDER')

import bpy,struct,math,os,time,sys,mathutils

#idem as a regular submesh but component vertices are not regular Cal3DVertex
class Cal3DBlendShapeSubMesh(object):
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

	def writeCal3D(self, file, matrix, matrix_normal):
		
		buff=('\t<SUBMESH NUMVERTICES="%i" NUMFACES="%i" MATERIAL="%i" ' % \
				(self.vert_count, len(self.faces), self.material.id))
		buff+=('NUMLODSTEPS="%i" NUMSPRINGS="%i" NUMTEXCOORDS="%i">\n' % \
				 (self.nb_lodsteps, len(self.springs),
				 len(self.material.maps_filenames)))
		
		i = 0
		for v in self.vertices:
			for item in v: #item is Cal3DBlendShapeVertex
				item.id = i
				buff+=item.writeCal3D(file, matrix, matrix_normal,len(self.material.maps_filenames))
				i += 1
		
		for item in self.springs:
			buff+=item.writeCal3D(file)
		for item in self.faces:
			buff+=item.writeCal3D(file)
		
		buff+=('\t</SUBMESH>\n')
		return buff	  

class Cal3DBlendShapeMesh(object):
	__slots__ = 'name', 'submeshes', 'matrix', 'matrix_normal','numBlendShape'
	def __init__(self, ob, blend_mesh, blend_world):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMaterial import Cal3DMaterial
		from .Cal3DSubMesh import Cal3DSubMesh
		self.name      = ob.name
		self.submeshes = [] #from submesh to submesh tabs 

		shapekeycpt=0
		ob.active_shape_key_index=shapekeycpt
		current_shapekey=ob.active_shape_key
		##For each shapekeys test existence (only way to know numbers of shapekeys???!!!:/)
		while current_shapekey!=None:
			shapekeycpt=shapekeycpt+1
			ob.active_shape_key_index=shapekeycpt
			current_shapekey=ob.active_shape_key
			
		self.numBlendShape=shapekeycpt-1
		
		  
class Cal3DBlendShapeMesh(object):
	__slots__ = 'name', 'submeshes', 'matrix', 'matrix_normal','numBlendShape',"blendshapes_names"
	def __init__(self, ob,  blend_world):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMaterial import Cal3DMaterial
		from .Cal3DMesh import Cal3DFace
		from .Cal3DBlendShapeVertex import Cal3DBlendShapeVertex
		from .Cal3DSkeleton import Cal3DSkeleton
		self.name      = ob.name
		self.submeshes = []
		self.blendshapes_names=[]		

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
			
		self.numBlendShape=shapekeycpt-1

		#temporary meshes create from shape keys 
		blend_meshes=[]
		#index 0 is base shape
		blend_meshes.append(ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE))	
		for shapekey_index in range(1,self.numBlendShape):
			ob.active_shape_key_index=shapekey_index
			ob.active_shape_key.value=1.0
			self.blendshapes_names.append(ob.active_shape_key.name)
			blend_meshes.append(ob.to_mesh(bpy.context.scene,APPLY_MODIFIERS,MESH_EXPORT_MODE))
			ob.active_shape_key.value=0.0
			
		
		#BPyMesh.meshCalcNormals(blend_mesh)
		for blend_mesh in blend_meshes:
			blend_mesh.calc_normals()
		self.matrix = ob.matrix_world.copy()
		#self.matrix= ob.matrix_local.copy()
		loc, rot, sca = self.matrix.copy().decompose()
		self.matrix_normal = rot.to_matrix() #mathutils.Matrix.Rotation(rot.angle, 4, rot.axis)
		
		#if BASE_MATRIX:
		#	matrix = matrix_multiply(BASE_MATRIX, matrix)
		
		face_groups = {}
		blend_materials = blend_meshes[0].materials
		uvlayers = ()
		mat = None # incase we have no materials
		print("UV number:%d\n"% len(blend_meshes[0].uv_textures))
		
		for mat_index,mat in enumerate(blend_meshes[0].materials):
			#create material if not already exists
			imagelist=[]
			for tex in ob.material_slots[mat_index].material.texture_slots:
				if tex :
					if tex.texture.type=='IMAGE':
						imagelist.append(tex.texture.image.filepath)
					else:
						#procedural stuff so do a shader for it
						print(tex.texture.type)
			material=None		
			#TODO:Fuck this shit out of my code
			try:		material = Cal3DMaterial.MATERIALS[mat, tuple(imagelist)]
			except:		material = Cal3DMaterial.MATERIALS[mat, tuple(imagelist)] = Cal3DMaterial(blend_world, mat, imagelist)		

			#create one submesh per material..
			submesh = Cal3DBlendShapeSubMesh(self, material, len(self.submeshes))
			self.submeshes.append(submesh)
			#use a vertex index map cause we visit faces and vertices may surely be duplicated
			#key index in mesh.vertices/value: index in submesh.vertices
			submesh_vertex_index_map={}
			#submeshfaces=[]
			for f in blend_meshes[0].tessfaces:
				if f.material_index==mat_index:
					#face is associated with the current mat so treat it
					#submeshfaces.append(f)
					normal=None
					if not f.use_smooth:
						#recompute normal 
						#WARNING:assuming triangle faces
						p1 = blend_meshes[0].vertices[ f.vertices[0] ].co
						p2 = blend_meshes[0].vertices[ f.vertices[1] ].co
						p3 = blend_meshes[0].vertices[ f.vertices[2] ].co
						vv1 =  mathutils.Vector((p3[0] - p2[0], p3[1] - p2[1], p3[2] - p2[2]))
						vv2= mathutils.Vector((p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]))
						normal=vv1.cross(vv2)	

					for facevertexindex,vert_index in enumerate(f.vertices):
						try:	indexinmap=submesh_vertex_index_map[vert_index]
						except: 
							submesh_vertex_index_map[vert_index]=len(submesh.vertices)
							#add vertex in submesh
							#crawl uvs
							uvs=[]
							for uv in blend_meshes[0].tessface_uv_textures:
								uvs.append(uv.data[f.index].uv[facevertexindex])
							#crawl bones influences
							influences = []	
							for vertex_group in blend_meshes[0].vertices[vert_index].groups:
								inf = [ob.vertex_groups[vertex_group.group ].name, vertex_group.weight]

								try:
									bone  = Cal3DSkeleton.BONES[ob.vertex_groups[vertex_group.group ].name] #look up cal3d_bone
								except:
									#print( str(vert_index )+"found an unknow vertex group: " + ob.vertex_groups[vertex_group.group ].name )
									continue
								if  inf[0]!="": influences.append( inf )
							#check if parent is a bone
							for j in range(1):
									try:
									    
										bone  = Cal3DSkeleton.BONES[ob.parent_bone] #look up cal3d_bone
									except:
										continue
									#this mesh has a parent_bone so generate inf for its
									#print(ob.parent_bone)
									#print("create parent that is not part of blender\n")
					
							inf = [ob.parent_bone,1.0]
							if len(influences)==0 and inf[0]!="": influences.append( inf )


							#for each shape keys add vertex and normal to lists
							shapekeysvertices=[]
							shapekeysnormals=[]
							for shapekey_index in range(1,self.numBlendShape):
								#get vertex normal if per vertex normal
								if f.use_smooth:
									normal=blend_meshes[shapekey_index-1].vertices[vert_index].normal
								shapekeysnormals.append(normal)
								shapekeysvertices.append(blend_meshes[shapekey_index-1].vertices[vert_index].co)
							#create CalVertex

							submesh.vertices.append([Cal3DBlendShapeVertex(shapekeysvertices,shapekeysnormals,uvs,influences)
#,
#Cal3DVertex(mathutils.Vector((0,0,0)),normal,uvs,influences) #dummy vertex to see what append at loading :it focking fails the spec...TODO write my own spec for blendshapes
])
					submesh.vert_count=len(submesh.vertices)

					#once CalVertices exists in sumesh, we can create CalFace
					#faces with more than 3 vertices are split in a triangles fans fashion 
					#WARNING: assume convex poly faces
					for i in range(1, len(f.vertices) - 1):
						submesh.faces.append(
							Cal3DFace(
							submesh.vertices[submesh_vertex_index_map[f.vertices[0]]][0],
							submesh.vertices[submesh_vertex_index_map[f.vertices[i]]][0],
							submesh.vertices[submesh_vertex_index_map[f.vertices[i+1]]][0]))	

					
	
	def writeCal3D(self, file):

		buff=('<?xml version="1.0"?>\n')
		buff+=('<HEADER MAGIC="XMF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<MESH NUMSUBMESH="%i" NUMBLENDSHAPE="%i">\n' %( len(self.submeshes) ,self.numBlendShape))
		#buff+=('<MESH NUMSUBMESH="%i">\n' % len(self.submeshes))
		#BlendShapes Naming
		for i,shapename in enumerate(self.blendshapes_names):
			buff+=('\t<BLENDSHAPE ID="%i" NAME="%s"/>\n' %( i ,shapename))
				
		
		for submesh in self.submeshes:
			buff+=submesh.writeCal3D(file, self.matrix, self.matrix_normal)
		buff+=('</MESH>\n')
		file.write(bytes(buff, 'UTF-8'));
