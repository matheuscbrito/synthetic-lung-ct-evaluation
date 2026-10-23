import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { Slice } from "../api";
import { imageUrl } from "../api";
import { IDENTITY, pan, zoomAt, type View } from "../zoom";

interface Props {
  version: string;
  slice: Slice;
}

const WHEEL_FACTOR = 1.2;

interface PaneProps {
  src: string;
  contourSrc: string | null;
  caption: string;
  view: View;
  setView: (update: (v: View) => View) => void;
}

// Um painel quadrado: imagem + contorno opcional, ambos com a mesma transformação da vista compartilhada.
function Pane({ src, contourSrc, caption, view, setView }: PaneProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);

  // wheel precisa de listener nativo não passivo para poder chamar preventDefault
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const factor = e.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR;
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      setView(v => zoomAt(v, factor, cx, cy));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [setView]);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    drag.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const last = drag.current;
    if (!last) return;
    drag.current = { x: e.clientX, y: e.clientY };
    const dx = e.clientX - last.x;
    const dy = e.clientY - last.y;
    setView(v => pan(v, dx, dy));
  };

  const endDrag = () => {
    drag.current = null;
  };

  return (
    <figure className="pane">
      <figcaption>{caption}</figcaption>
      <div
        ref={viewport}
        className="viewport"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={() => setView(() => IDENTITY)}
      >
        <div
          className="canvas"
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
        >
          <img className="base" src={src} alt={caption} draggable={false} />
          {contourSrc !== null && (
            <img className="contour" src={contourSrc} alt="" draggable={false} />
          )}
        </div>
      </div>
    </figure>
  );
}

// Real · Sintética · |Diff| com zoom/pan compartilhados; |Diff| some em modo só máscara.
export function ImageRow({ version, slice }: Props) {
  const [view, setView] = useState<View>(IDENTITY);
  const [roi, setRoi] = useState(true);
  const showDiff = !slice.mask_only;
  const contour = roi ? imageUrl(version, slice.case_id, "contour") : null;

  return (
    <section className="image-row-wrap">
      <div className="roi-toggle">
        <label>
          <input type="checkbox" checked={roi} onChange={e => setRoi(e.target.checked)} />
          ROI
        </label>
      </div>
      <div className="image-row" style={{ gridTemplateColumns: `repeat(${showDiff ? 3 : 2}, minmax(0, 1fr))` }}>
        <Pane
          src={imageUrl(version, slice.case_id, "real")}
          contourSrc={contour}
          caption="Real"
          view={view}
          setView={setView}
        />
        <Pane
          src={imageUrl(version, slice.case_id, "synthetic")}
          contourSrc={contour}
          caption="Synthetic"
          view={view}
          setView={setView}
        />
        {showDiff && (
          <Pane
            src={imageUrl(version, slice.case_id, "diff")}
            contourSrc={contour}
            caption="|Diff|"
            view={view}
            setView={setView}
          />
        )}
      </div>
    </section>
  );
}
