CAL3D_VERSION = 910

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
	
	def getVertex(self, ob, mesh,blend_vert, normal, maps):
		from .Cal3DVertex import Cal3DVertex
		from .Cal3DSkeleton import Cal3DSkeleton
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
			for j in range(len(mesh.vertices[blend_index].groups )):
				inf = [ob.vertex_groups[ mesh.vertices[ blend_index ].groups[j].group ].name, mesh.vertices[blend_index].groups[j].weight]
				#print(ob.vertex_groups[ ob.data.vertices[ blend_index ].groups[j].group ].name)
				try:
					bone  = Cal3DSkeleton.BONES[ob.vertex_groups[ mesh.vertices[ blend_index ].groups[j].group ].name] #look up cal3d_bone
				except:
					#print( "found an unknow vertex group: " + ob.vertex_groups[ ob.data.vertices[ blend_index ].groups[j].group ].name )
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
				buff+=item.writeCal3D(file, matrix, matrix_normal,len(self.material.maps_filenames))
				i += 1
		
		for item in self.springs:
			buff+=item.writeCal3D(file)
		for item in self.faces:
			buff+=item.writeCal3D(file)
		
		buff+=('\t</SUBMESH>\n')
		return buff;
