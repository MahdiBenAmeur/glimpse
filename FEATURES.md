# FindAnything Features and Supported Functionality

## Overview

FindAnything is a local-first photo discovery and organization application built around semantic search, face clustering, collection management, and interactive indexing. The application combines a frontend desktop-style experience with a backend that manages indexing, vector stores, metadata, thumbnails, and search operations.

At a high level, the application lets a user:

- choose and manage an embedding model
- add folders and image files from the local machine
- index and reindex a photo library
- search by text, by image, by person, and by advanced filters
- detect and review people found in the library
- rename people clusters
- browse, create, and manage collections
- save and rerun searches
- open original files outside the app
- manage thumbnail cache and inspect storage usage

This document lists the currently supported product features and the intended functionality available from the application.

## 1. Model Setup and Management

The application supports local model-driven indexing and search.

### Available functionality

- list available embedding models
- show whether a model is not installed, installed, downloading, or active
- download supported models
- activate a model for search and indexing
- switch models from settings
- switch model and rebuild the index so embeddings stay consistent

### Current behavior

- the active model is persisted by the backend
- model activation is required before indexing
- switching the active model can trigger a full rebuild of vector stores
- model removal is not currently wired as a full product feature

## 2. Library Input and Import

The application can ingest photos from the local machine using native file and folder pickers.

### Available functionality

- add a folder path through a folder picker
- add individual photos or multiple photos through a file picker
- include subfolders when indexing folders
- import selected images into the managed library flow
- avoid reindexing the same image path twice

### Current behavior

- folder paths are normalized and deduplicated
- repeated indexing of the same canonical path is skipped
- imported and indexed files become available to search, collections, and people views

## 3. Indexing and Reindexing

Indexing is the core workflow that prepares the photo library for search and people detection.

### Available functionality

- start indexing from the onboarding flow
- start indexing from the index page
- reindex the whole library
- reindex specific folders
- index newly added photos
- run indexing in the background while using the rest of the application
- track indexing progress

### Indexing pipeline behavior

- scan folders and collect supported image files
- compute image embeddings using the active vision-language model
- detect faces in images
- compute face embeddings
- update person centroids
- generate and serve thumbnails
- persist image and face vector stores
- update metadata and folder statistics

### Progress data available in the app

- indexing phase
- overall progress percentage
- processed file count
- total file count
- detected face count
- current file being processed

## 4. Search

Search is one of the primary product surfaces and supports several discovery modes.

### Text search

- natural-language search over indexed images
- semantic retrieval based on image embeddings
- result scoring

### Search by image

- use an indexed image to find similar images
- drag and drop an image into the search page to search by image
- choose an image file from disk and search for visually similar results

### People-aware search

- include people in a search
- express person preferences such as must include, prefer, or exclude

### Advanced filters

- filter by folder
- filter by date range
- filter by face presence
- combine filters with text search

### Search UI behavior

- search results display thumbnails
- loading skeletons appear while a search request is running
- result cards open into an image viewer
- active filters are shown and can be cleared

## 5. Results and Image Viewing

Indexed images can be viewed both as search results and as items inside people and collection pages.

### Available functionality

- show thumbnails for indexed images
- load full image data when a full image view is needed
- open an image in the in-app viewer
- navigate between images in the viewer
- close the viewer using the top-left close button
- favorite and unfavorite images
- find similar images directly from the viewer
- open the original image externally from the viewer
- copy the original image path from the viewer

### Metadata shown in the viewer

- filename
- folder
- date taken
- dimensions
- face count
- people tags
- collections
- similarity score when relevant
- original image path when available

### Date behavior

- the app uses stored metadata when available
- if no stored capture time exists, the backend falls back to available image metadata
- if no image metadata exists, filesystem time can be used as a fallback

## 6. Favorites

The application supports lightweight personal curation through favorites.

### Available functionality

- toggle favorite status on indexed images
- keep favorite state in backend-managed library state
- view favorited images in a dedicated favorites flow

## 7. People Detection and People Management

The application groups detected faces into person clusters based on face embeddings and centroid updates.

### Available functionality

- detect people from indexed images
- generate a people list from face clustering results
- display a face preview for each detected person
- show image count for each person
- show last seen information when available
- open a person detail page
- view images associated with a person
- rename a person cluster

### Current behavior

- people are backed by the person vector store metadata
- renaming updates the stored person entry name
- the people list now returns the full dataset instead of clipping at a low default limit

### Not currently enabled in the product UI

- merge people
- split people

These actions were intentionally removed from the interface for now and can be added later.

## 8. Collections

Collections let the user curate and organize selected images.

### Available functionality

- create a collection
- rename a collection
- delete a collection
- browse all collections
- open a collection detail page
- view all images in a collection
- add photos to a collection through a picker
- remove photos from a collection
- display collection preview thumbnails

### Collection add behavior

- if a chosen image is already indexed, it can be added directly
- if a chosen image is not indexed yet, the backend can auto-index it and then add it to the collection

## 9. Saved Searches

The application supports saving search presets for repeated use.

### Available functionality

- save the current query and filters as a named saved search
- list saved searches
- delete saved searches
- rerun a saved search from the saved searches page

### Saved search data can include

- query text
- folder filters
- date range filters
- face presence filters
- people selection

## 10. Storage and Cache Management

The backend keeps track of persistent data used by the application.

### Storage areas used by the app

- SQLite database
- image vector store
- face vector store
- person vector store
- thumbnail cache
- library state
- saved searches state
- model state

### Available functionality

- show real index storage size from disk
- show thumbnail cache size from disk
- clear thumbnail cache
- keep model files separate from library reset scripts

## 11. Desktop and Local Machine Integration

The application includes several flows that interact with the local machine directly.

### Available functionality

- open native folder picker
- open native image picker
- open original image externally with the system default app
- copy original file path to clipboard
- read image files from local disk

## 12. Backend Services and Internal Capabilities

The backend currently supports the following application-level capabilities.

### API capabilities

- model listing
- model download
- model activation
- index summary
- indexing status
- index start and rebuild
- storage summary
- clear cache
- folder CRUD and folder picking
- image listing and favorite toggling
- people listing, person detail, person images, person face preview, and person rename
- collections CRUD and collection image membership management
- saved searches CRUD
- semantic search
- search by image
- serving thumbnails and full images

### Internal data behaviors

- live in-memory and persisted vector store handling
- path normalization for deduplication
- image metadata fallback handling
- thumbnail generation and caching
- library state persistence for favorites and collection membership

## 13. Helper Scripts

The repository also contains helper scripts for maintenance and review tasks.

### Current script capabilities

- reset application library data while preserving model files
- inspect person centroid similarity
- generate merge-review groups for people centroid analysis
- export one representative face image per person into merge group folders

## 14. Current Product Boundaries

The following capabilities are not fully implemented or are intentionally limited at the moment.

### Not fully implemented yet

- full model uninstall flow
- people merge action from the main UI
- people split action from the main UI
- advanced conflict review flow for person merges
- richer bulk operations across multiple result items

### Operational assumptions

- the application is designed around local file access
- indexing depends on a selected embedding model
- search quality depends on successful indexing and vector-store consistency

## 15. Intended User Flow Summary

The intended end-to-end flow of the application is:

1. choose or download a model
2. add folders or image files
3. start indexing
4. wait for embeddings, faces, and thumbnails to be generated
5. search using text, filters, people, or an example image
6. inspect results in the viewer
7. favorite images, organize them into collections, and save useful searches
8. manage people names and keep the library organized over time

