CAL3D_VERSION = 1100
from array import array


def cleanJapaneseString(v):
#convert not recognized character to hexa and suppress \x
	return str(v.encode('utf_8')).replace("\\x","")[2:len(str(v.encode('utf_8')).replace("\\x",""))-1]	  
	
class Cal3DInfluence(object):
	__slots__ = 'bone', 'weight'
	def __init__(self, bone, weight):
		self.bone   = bone
		self.weight = weight
	
	def writeCal3D(self, file):
		return('\t\t\t<INFLUENCE ID="%i">%.6f</INFLUENCE>\n' % \
					 (self.bone.id, self.weight))
	def to_cal3d_binary(self, file):
                ar = array('L', [self.bone.id])
                ar.tofile(file)
                ar = array('f', [self.weight])
                ar.tofile(file)

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
	def to_cal3d_binary(self, file):
		ar = array('L', [self.vertex1.id, self.vertex2.id, self.vertex3.id])
		ar.tofile(file)
		  

		  

class Cal3DMesh(object):
	__slots__ = 'name', 'submeshes', 'matrix', 'matrix_normal'
	def __init__(self, ob, blend_mesh, blend_world):
		import bpy,struct,math,os,time,sys,mathutils
		from .Cal3DMaterial import Cal3DMaterial
		from .Cal3DSubMesh import Cal3DSubMesh
		from .Cal3DVertex import Cal3DVertex
		from .Cal3DSkeleton import Cal3DSkeleton
		self.name      = cleanJapaneseString(ob.name)
		self.submeshes = []
		
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
		
		for mat_index,mat in enumerate(blend_mesh.materials):
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
			submesh = Cal3DSubMesh(self, material, len(self.submeshes))
			
			#use a vertex index map cause we visit faces and vertices may surely be duplicated
			#key index in mesh.vertices/value: index in submesh.vertices
			submesh_vertex_index_map={}
			#submeshfaces=[]
			for f in blend_mesh.tessfaces:
				if f.material_index==mat_index:
					#face is associated with the current mat so treat it
					#submeshfaces.append(f)
					normal=None
					if not f.use_smooth:
						#recompute normal 
						#WARNING:assuming triangle faces
						p1 = blend_mesh.vertices[ f.vertices[0] ].co
						p2 = blend_mesh.vertices[ f.vertices[1] ].co
						p3 = blend_mesh.vertices[ f.vertices[2] ].co
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
							for uv in blend_mesh.tessface_uv_textures:
								uvs.append(uv.data[f.index].uv[facevertexindex])
							#crawl bones influences
							influences = []	
							for vertex_group in blend_mesh.vertices[vert_index].groups:
								inf = [ob.vertex_groups[vertex_group.group ].name, vertex_group.weight]

								try:
									bone  = Cal3DSkeleton.BONES[inf[0]] #look up cal3d_bone
								except:
									#CHECK MODEL EXCEPTIONS HERE
									#CHECK FOR 'VIS' POSTFIX (FRANKIE.blend)
									if inf[0][0:len(inf[0])-3]+'VIS'==inf[0]:
										inf [0]= inf[0][0:len(inf[0])-3]
										try:
											bone  = Cal3DSkeleton.BONES[inf[0]] #look up cal3d_bone
											#print("'VIS' POSTFIX (FRANKIE.blend) vertex group: " + ob.vertex_groups[vertex_group.group ].name )
											continue
										except:
											#print( str(vert_index )+"found an unknow vertex group: " + ob.vertex_groups[vertex_group.grosup ].name )
											continue
									else:continue
									continue
								if  inf[0]!="" and inf[1]>0: influences.append( inf )
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
							#get vertex normal if per vertex normal
							if f.use_smooth:
								normal=blend_mesh.vertices[vert_index].normal
							#create CalVertex
							submesh.numtexcoord=len(uvs)
							submesh.vertices.append([Cal3DVertex(blend_mesh.vertices[vert_index].co,normal,uvs,influences)
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
			if len(submesh.faces)!=0 : #unused material
				self.submeshes.append(submesh)
									
	
	
	def writeCal3D(self, file):

		buff=('<?xml version="1.0"?>\n')
		#buff+=('<HEADER MAGIC="XMF" VERSION="%i"/>\n' % CAL3D_VERSION)
		#buff+=('<MESH NUMSUBMESH="%i">\n' % len(self.submeshes))
		buff+=('<MESH MAGIC="XMF" VERSION="%i" ' % CAL3D_VERSION)
		buff+=('NUMSUBMESH="%i">\n' % len(self.submeshes))
		for submesh in self.submeshes:
			buff+=submesh.writeCal3D(file, self.matrix, self.matrix_normal)
		buff+=('</MESH>\n')
		file.write(bytes(buff, 'UTF-8'))
		
	def to_cal3d_binary(self, file):
		from array import array
		s = b'CMF\0'
		ar = array('b', list(s))
		ar.tofile(file)

		ar = array('L', [1100])
		ar.tofile(file)

		ar = array('L', [len(self.submeshes)])
		ar.tofile(file)

		for sm in self.submeshes:
				sm.to_cal3d_binary(file, self.matrix, self.matrix_normal)
