package com.imt.framework.web.tuto.resources;

import com.imt.framework.web.tuto.entities.Livre;
import com.imt.framework.web.tuto.repositories.LivreRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import jakarta.ws.rs.core.Response;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class LivreResourceTest {

	@Mock
	private LivreRepository livreRepository;

	@InjectMocks
	private LivreResource livreResource;

	@BeforeEach
	void setUp() {
		MockitoAnnotations.openMocks(this);
	}

	@Test
	void testGetBooksWithoutMaxPrice() {
		// Arrange
		Livre livre1 = new Livre(1, "Title1", "Author1", 10.0);
		Livre livre2 = new Livre(2, "Title2", "Author2", 20.0);
		List<Livre> livres = Arrays.asList(livre1, livre2);

		when(livreRepository.findAll()).thenReturn(livres);

		// Act
		Response response = livreResource.getBooks(null);

		// Assert
		assertEquals(Response.Status.OK.getStatusCode(), response.getStatus());
		assertEquals(livres, response.getEntity());
		verify(livreRepository, times(1)).findAll();
	}

	@Test
	void testGetBooksWithMaxPrice() {
		// Arrange
		Double maxPrice = 15.0;
		Livre livre = new Livre(1, "Title1", "Author1", 10.0);
		List<Livre> livres = Arrays.asList(livre);

		when(livreRepository.getBooksWithMaxPrice(maxPrice)).thenReturn(livres);

		// Act
		Response response = livreResource.getBooks(maxPrice);

		// Assert
		assertEquals(Response.Status.OK.getStatusCode(), response.getStatus());
		assertEquals(livres, response.getEntity());
		verify(livreRepository, times(1)).getBooksWithMaxPrice(maxPrice);
	}

	@Test
	void testCreateBook() {
		// Arrange
		Livre livre = new Livre(1, "Title", "Author", 10.0);

		// Act
		livreResource.createBook(livre);

		// Assert
		verify(livreRepository, times(1)).save(livre);
	}

	@Test
	void testUpdateBook() throws Exception {
		// Arrange
		Integer id = 1;
		Livre existingLivre = new Livre(id, "Old Title", "Old Author", 15.0);
		Livre updatedLivre = new Livre(id, "New Title", "New Author", 20.0);

		when(livreRepository.findById(id)).thenReturn(Optional.of(existingLivre));

		// Act
		livreResource.updateBook(id, updatedLivre);

		// Assert
		verify(livreRepository, times(1)).save(existingLivre);
		assertEquals("New Title", existingLivre.getTitre());
		assertEquals("New Author", existingLivre.getAuteur());
		assertEquals(20.0, existingLivre.getPrice());
	}

	@Test
	void testUpdateBookThrowsExceptionWhenNotFound() {
		// Arrange
		Integer id = 1;
		Livre updatedLivre = new Livre(id, "New Title", "New Author", 20.0);

		when(livreRepository.findById(id)).thenReturn(Optional.empty());

		// Act & Assert
		Exception exception = assertThrows(Exception.class, () -> {
			livreResource.updateBook(id, updatedLivre);
		});
		assertEquals("Livre inconnu", exception.getMessage());
		verify(livreRepository, never()).save(any(Livre.class));
	}

	@Test
	void testDeleteBook() {
		// Arrange
		Integer id = 1;

		// Act
		livreResource.deleteBook(id);

		// Assert
		verify(livreRepository, times(1)).deleteById(id);
	}
}