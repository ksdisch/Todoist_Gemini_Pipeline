# Material/Tailwind inspired colors
# Need to ensure these work well with Fusion style

class Palette:
    LIGHT = {
        "window_bg": "#F3F4F6", # Light gray (Tailwind gray-100)
        "surface_bg": "#FFFFFF",
        "text_primary": "#1F2937", # gray-800
        "text_secondary": "#6B7280", # gray-500
        "border": "#E5E7EB", # gray-200
        "primary": "#2563EB", # blue-600
        "primary_hover": "#1D4ED8", # blue-700
        "primary_text": "#FFFFFF",
        "danger": "#DC2626", # red-600
        "success": "#10B981", # emerald-500
        "warning": "#F59E0B", # amber-500
        "action_row_alt": "#F9FAFB", # gray-50
        "selection": "#BFDBFE", # blue-200 (for table selection)
        "selection_text": "#1F2937",
    }

    DARK = {
        "window_bg": "#111827", # gray-900
        "surface_bg": "#1F2937", # gray-800
        "text_primary": "#F9FAFB", # gray-50
        "text_secondary": "#9CA3AF", # gray-400
        "border": "#374151", # gray-700
        "primary": "#3B82F6", # blue-500
        "primary_hover": "#60A5FA", # blue-400
        "primary_text": "#FFFFFF",
        "danger": "#EF4444", # red-500
        "success": "#34D399", # emerald-400
        "warning": "#FBBF24", # amber-400
        "action_row_alt": "#1F2937", # Same as surface (or slightly lighter: #374151)
        "selection": "#2563EB", # blue-600
        "selection_text": "#FFFFFF",
    }
