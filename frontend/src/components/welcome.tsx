import { useOutletContext } from "react-router";
import type { TravelActions } from "./layout";
import { TravelForm } from "./travel-form";

export function Welcome() {
  const { create, creating } = useOutletContext<TravelActions>();

  return (
    <section className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto max-w-2xl px-4 py-6 sm:px-8 sm:py-12">
        {/* 纯净表单卡片 */}
        <TravelForm busy={creating} onSubmit={(text) => void create(text)} />
      </div>
    </section>
  );
}
