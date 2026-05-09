import { useState } from 'react';

interface ImageViewerProps {
  src: string;
  alt: string;
}

export function ImageViewer({ src, alt }: ImageViewerProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  const handleDownload = async () => {
    try {
      const response = await fetch(src);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `image-${Date.now()}.jpg`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download image:', error);
    }
  };

  const handleFullscreen = () => {
    setIsFullscreen(true);
  };

  const handleCloseFullscreen = () => {
    setIsFullscreen(false);
  };

  return (
    <>
      {/* Image Container */}
      <div className="my-3 rounded-lg overflow-hidden bg-slate-200 dark:bg-slate-700 inline-block">
        <div className="relative group">
          {/* Loading Skeleton */}
          {!imageLoaded && (
            <div className="w-80 h-64 bg-gradient-to-r from-slate-300 to-slate-400 dark:from-slate-600 dark:to-slate-700 animate-pulse" />
          )}

          {/* Image */}
          <img
            src={src}
            alt={alt}
            onLoad={() => setImageLoaded(true)}
            className={`max-w-2xl max-h-96 object-cover cursor-pointer transition-opacity ${
              imageLoaded ? 'opacity-100' : 'opacity-0 absolute'
            }`}
          />

          {/* Overlay Buttons - Visible on Hover */}
          {imageLoaded && (
            <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all duration-200 flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100">
              {/* Fullscreen Button */}
              <button
                onClick={handleFullscreen}
                className="bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-lg"
                title="Open in fullscreen"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 6H6v12h12v-4m4-7h-4v4m4-11V3m0 4v4"
                  />
                </svg>
              </button>

              {/* Download Button */}
              <button
                onClick={handleDownload}
                className="bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-lg"
                title="Download image"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4"
          onClick={handleCloseFullscreen}
        >
          <div
            className="relative max-w-5xl max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={handleCloseFullscreen}
              className="absolute top-4 right-4 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors z-10"
              title="Close fullscreen"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>

            {/* Fullscreen Image */}
            <img
              src={src}
              alt={alt}
              className="w-full h-full object-contain"
            />

            {/* Download Button in Fullscreen */}
            <button
              onClick={handleDownload}
              className="absolute bottom-4 right-4 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-lg p-3 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-lg"
              title="Download image"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
