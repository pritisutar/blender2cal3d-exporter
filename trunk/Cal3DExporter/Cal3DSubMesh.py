
class Cal3DSubMesh(object):
	__slots__ = 'material', 'vertices', 'vert_mapping', 'vert_count', 'faces', 'nb_lodsteps', 'springs','numtexcoord', 'id'
	def __init__(self, mesh, material, id):
		self.material   = material
		self.vertices   = []
		self.vert_mapping = dict() # map original indicies to local
		self.vert_count = 0
		self.faces      = []
		self.nb_lodsteps = 0
		self.springs    = []
		self.id = id
		self.numtexcoord=0
	
	
		
	
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
				 self.numtexcoord))
		
		i = 0
		for v in self.vertices:
			for item in v:
				item.id = i
				buff+=item.writeCal3D(file, matrix, matrix_normal,self.numtexcoord)
				i += 1
		
		for item in self.springs:
			buff+=item.writeCal3D(file)
		for item in self.faces:
			buff+=item.writeCal3D(file)
		
		buff+=('\t</SUBMESH>\n')
		return buff;
	def to_cal3d_binary(self, file, matrix, matrix_normal):
		from array import array
		#self.vertices = sorted(self.vertices, key=attrgetter('index'))
		texcoords_num = self.numtexcoord
		#if self.vertices and len(self.vertices) > 0:
		#		texcoords_num = len(self.vertices[0].maps)

		#faces_num = 0
		#for face in self.faces:
				#if face.vertex4:
				#		faces_num += 2
				#else:
				#		faces_num += 1

		ar = array('l', [self.material.id,
										 len(self.vertices),
										 len(self.faces),
										 self.nb_lodsteps,
										 len(self.springs),
										 texcoords_num])
		ar.tofile(file)
		i=0
		for vt in self.vertices:
			for item in vt:
				item.id = i
				item.to_cal3d_binary(file, matrix, matrix_normal,self.numtexcoord)
				i += 1
				

		if self.springs and len(self.springs) > 0:
				for sp in self.springs:
						sp.to_cal3d_binary(file)

		for fc in self.faces:
				fc.to_cal3d_binary(file)
