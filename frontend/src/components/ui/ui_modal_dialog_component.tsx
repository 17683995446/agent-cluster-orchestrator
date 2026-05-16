import { ReactNode } from 'react';
import { X } from 'lucide-react';
import { Button } from './ui_button_component';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({ isOpen, onClose, title, children, footer }: ModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/60 transition-opacity" onClick={onClose} />
        <div className="relative bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md shadow-xl">
          <div className="flex items-center justify-between p-6 border-b border-slate-700">
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-5 w-5" />
            </Button>
          </div>
          <div className="p-6">{children}</div>
          {footer && (
            <div className="flex justify-end gap-3 p-6 border-t border-slate-700">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
