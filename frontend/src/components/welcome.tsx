import { useState } from "react";
import { useOutletContext } from "react-router";
import type { TravelActions } from "./layout";
import { TravelForm, travelPrompt } from "./travel-form";
import { Composer } from "./composer";

export function Welcome() {
  const { create, creating } = useOutletContext<TravelActions>();
  const [values, setValues] = useState<Record<string, string>>({});

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <section className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-8">
        <div className="mx-auto max-w-2xl py-6 sm:py-12">
          <TravelForm values={values} onChange={setValues} />
        </div>
      </section>
      <Composer
        busy={creating}
        hasFormValues={Object.values(values).some((value) => value.trim())}
        onSend={(text) => create(travelPrompt(values, text))}
      />
    </div>
  );
}
