package com.imt.framework.web.tuto.entities;

import jakarta.persistence.*;

@Entity
public class Livre {
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Integer id;
    private String titre;
    private String auteur;
    private Double price;

    // Constructeur par défaut
    public Livre() {
    }

    // Constructeur paramétré
    public Livre(Integer id, String titre, String auteur, Double price) {
        this.id = id;
        this.titre = titre;
        this.auteur = auteur;
        this.price = price;
    }

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getTitre() {
        return titre;
    }

    public void setTitre(String titre) {
        this.titre = titre;
    }

    public String getAuteur() {
        return auteur;
    }

    public void setAuteur(String auteur) {
        this.auteur = auteur;
    }

    public Double getPrice() {
        return price;
    }

    public void setPrice(Double price) {
        this.price = price;
    }
}
