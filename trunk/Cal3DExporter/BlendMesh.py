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
	

import bpy,struct,math,os,time,sys,mathutils
		  
class Cal3DBlendShapeMesh(object):
	__slots__ = 'name', 'submeshes', 'matrix', 'matrix_normal','numBlendShape'
	def __init__(self, ob, blend_mesh, blend_world,numBlendshape):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMaterial import Cal3DMaterial
		from .Cal3DSubMesh import Cal3DSubMesh
		self.name      = ob.name
		self.submeshes = [] #from submesh to submesh tabs 
		self.numBlendShape=numBlendshape
		
		#BPyMesh.meshCalcNormals(blend_mesh)
		blend_mesh.calc_normals()
		self.matrix = ob.matrix_world.copy()
		#self.matrix= ob.matrix_local.copy()
		loc, rot, sca = self.matrix.copy().decompose()
		self.matrix_normal = rot.to_matrix() #mathutils.Matrix.Rotation(rot.angle, 4, rot.axis)
		
		#if BASE_MATRIX:
		#	matrix = matrix_multiply(BASE_MATRIX, matrix)
		
		face_groups = {}
		blend_materials = blend_mesh.materials
		uvlayers = ()
		mat = None # incase we have no materials
		print("UV number:%d\n"% len(blend_mesh.uv_textures))
		if len(blend_mesh.uv_textures)>0:
			uvlayers = blend_mesh.uv_textures
			if len(uvlayers) == 1:
				for f in blend_mesh.tessfaces:
					try:
						mat0=ob.data.materials[f.material_index]
					
						if mat0:
							tex0=mat0.texture_slots[0]
						
							if tex0 and tex0.texture.type=='IMAGE':
								#print(tex0.texture.type)
								image=tex0.texture.image.filepath
							else: 
								image="debug this...image MUST BE SOMETHING TO GENERATE...texcoord i tkhink..must see"
								image =	ob.data.materials[f.material_index].name
								#image =""
									#(f.image,)  bit in a tuple so we can match multi UV code
						if blend_materials:	mat =	blend_materials[f.material_index] # if no materials, mat will always be None
						face_groups.setdefault( (mat,image), (mat,image,[]) )[2].append( f )
					except:
						print(blend_mesh)
						print("Warning:no material assigned")
			else:
				# Multi UV's
				face_multi_images = [[] for i in range(len(blend_mesh.data.tessfaces))]
				face_multi_uvs = [[[] for i in range(len(f))  ] for f in blend_mesh.data.tessfaces]
				for uvlayer in uvlayers:
					blend_mesh.activeUVLayer = uvlayer
					for i, f in enumerate(blend_mesh.tessfaces):
						face_multi_images[i].append(f.image)
						if f.image:
							for j, uv in enumerate(f.uv):
								face_multi_uvs[i][j].append( tuple(uv) )
				
				# Convert UV's to tuples so they can be compared with eachother
				# when creating new verts
				for fuv in face_multi_uvs:
					for i, uv in enumerate(fuv):
						fuv[i] = tuple(uv)
				
				for i, f in enumerate(blend_mesh.tessfaces):
					image =						tuple(face_multi_images[i])
					if blend_materials: mat =	blend_materials[f.material_index]
					face_groups.setdefault( (mat,image), (mat,image,[]) )[2].append( f )
		else:
			# No UV's
			#TODO:ADD VERTEX COLOR ELSE THE TINYXML CAL3DIMPORTER SHOULD FAIL LATTER WHEN USE IT:FOR THE MOMENT DONT EXPORT NO UV MESHES....
			for f in blend_mesh.tessfaces:
				if blend_materials: mat =	blend_materials[f. material_index]
				face_groups.setdefault( (mat,()), (mat,(),[]) )[2].append( f )
		
		for blend_material, blend_images, faces in face_groups.values():
			#print(blend_images)
			#print("newmaterial")
			try:		material = Cal3DMaterial.MATERIALS[blend_material, blend_images]
			except:		material = Cal3DMaterial.MATERIALS[blend_material, blend_images] = Cal3DMaterial(blend_world, blend_material, blend_images)
			
			submesh = Cal3DBlendShapeSubMesh(self, material, len(self.submeshes))
			self.submeshes[shapekey_name].append(submesh)
			
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
						
						vertex = submesh.getVertex(ob,blend_mesh, blend_vert, normal, face_multi_uvs[face.index][i])
						face_vertices.append(vertex)
				
				elif len(uvlayers)==1:
				

					if write_single_layer_uvs:
						face_uv =[]#face.uv
						for i in range(len(face.vertices)):
							face_uv.append([blend_mesh.tessface_uv_textures.active.data[face.index].uv[i][0], blend_mesh.tessface_uv_textures.active.data[face.index].uv[i][1]])
					
					for i, blend_vert in enumerate(face_v):
						if face.use_smooth:		normal =blend_mesh.vertices[ face.vertices[i] ].normal
						
						if write_single_layer_uvs:	uvs = (tuple(face_uv[i]),)
						else:						uvs = ()
						
						vertex = submesh.getVertex(ob,blend_mesh, blend_vert, normal, uvs )	
						face_vertices.append(vertex)
				else:
					# No UVs
					for i, blend_vert in enumerate(face_v):
						if face.use_smooth:		normal = blend_vert.normal
						vertex = submesh.getVertex(ob,blend_mesh, blend_vert, normal, () )
						face_vertices.append(vertex)
				
				
				# Split faces with more than 3 vertices
				for i in range(1, len(face.vertices) - 1):
					submesh.faces.append(Cal3DFace(face_vertices[0], face_vertices[i], face_vertices[i + 1]))
	
	def writeCal3D(self, file):

		buff=('<?xml version="1.0"?>\n')
		buff+=('<HEADER MAGIC="XMF" VERSION="%i"/>\n' % CAL3D_VERSION)
		buff+=('<MESH NUMSUBMESH="%i" NUMBLENDSHAPE="%i">\n' % len(self.submeshes) ,numBlendShape)
		for submesh in self.submeshes:
			buff+=submesh.writeCal3D(file, self.matrix, self.matrix_normal)
		buff+=('</MESH>\n')
		file.write(bytes(buff, 'UTF-8'));
