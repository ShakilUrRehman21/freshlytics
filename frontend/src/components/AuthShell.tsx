import { ReactNode } from 'react';
import Logo from './Logo';
import Sticker from './Sticker';

const AuthShell = ({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) => (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr]">
        <section className="relative hidden lg:flex flex-col justify-between bg-rail text-[#E9F2E2] p-12 overflow-hidden">
            <Logo className="text-[#F2F7EC]" />

            <div className="relative max-w-[460px]">
                <h1 className="font-display font-extrabold text-[56px] leading-[0.98] text-[#F2F7EC]">
                    Know which fruit to eat first.
                </h1>
                <p className="mt-6 text-[17px] text-[#B9CEB2] max-w-[38ch]">
                    Photograph your fruit bowl. Freshlytics spots decay, scores freshness and tells you how long
                    each piece has left — so less ends up in the bin.
                </p>
            </div>

            {/* A small cluster of score stickers, like a crate at the market */}
            <div className="relative h-[170px]" aria-hidden>
                <Sticker score={96} stage="Fresh" fruit="apple" size="lg" className="absolute left-0 bottom-2" />
                <Sticker score={64} stage="Good" fruit="banana" size="md" className="absolute left-[190px] bottom-[70px] rotate-6" />
                <Sticker score={38} stage="Use Soon" fruit="mango" size="md" className="absolute left-[230px] bottom-0" />
                <Sticker score={8} stage="Spoiled" size="sm" className="absolute left-[352px] bottom-[52px]" />
            </div>
        </section>

        <section className="flex flex-col justify-center px-6 py-12 sm:px-12">
            <div className="w-full max-w-[400px] mx-auto">
                <Logo className="lg:hidden text-leaf mb-10" />
                <h2 className="font-display font-bold text-[34px] leading-tight">{title}</h2>
                <p className="mt-2 text-muted">{subtitle}</p>
                <div className="mt-8">{children}</div>
            </div>
        </section>
    </div>
);

export default AuthShell;
