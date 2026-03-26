export interface Document {
  id: string;
  sharePointItemId: string;
  title: string;
  siteId: string;
  driveId: string;
  contentType: string;
  fileType: string;
  sharePointUrl: string;
  uploadedAt: string;
  textSegments?: TextSegment[];
}

export interface TextSegment {
  id: string;
  documentId: string;
  content: string;
  chunkIndex: number;
  vectorStoreId: string;
  createdAt: string;
}
