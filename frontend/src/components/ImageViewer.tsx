import { useState } from "react";
import { RotateCw, ZoomIn, ZoomOut, Maximize } from "lucide-react";
import { useAuthImage } from "../lib/api";
import { Button, Spinner } from "./ui";

export function ImageViewer({ src, alt = "Answer image", height = "70vh" }: { src: string | null; alt?: string; height?: string }) {
  const { url, error } = useAuthImage(src);
  const [zoom, setZoom] = useState(1);
  const [rot, setRot] = useState(0);
  return <div>
    <div className="mb-2 flex items-center gap-2">
      <Button variant="secondary" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(4, z + 0.25))}><ZoomIn className="h-4 w-4" /></Button>
      <Button variant="secondary" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}><ZoomOut className="h-4 w-4" /></Button>
      <Button variant="secondary" aria-label="Fit to screen" onClick={() => { setZoom(1); setRot(0); }}><Maximize className="h-4 w-4" /></Button>
      <Button variant="secondary" aria-label="Rotate" onClick={() => setRot((r) => (r + 90) % 360)}><RotateCw className="h-4 w-4" /></Button>
      <span className="text-xs text-slate-500">{Math.round(zoom * 100)}%</span>
    </div>
    <div className="overflow-auto rounded-md border bg-slate-100 p-2" style={{ height }}>
      {error ? <p className="p-4 text-sm text-red-600">{error}</p> : !url ? <Spinner label="Loading image…" /> :
        <img src={url} alt={alt} style={{ width: `${zoom * 100}%`, transform: `rotate(${rot}deg)`, transformOrigin: "top left", maxWidth: "none" }} />}
    </div></div>;
}
