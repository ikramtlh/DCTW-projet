import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socketio
import numpy as np
import math
import sys

# Server URL
SERVER_WS = "http://192.168.1.19:5003"

# Structure: [weight, P, Q, V] for each criterion
DECIDER_PREFS = {
    "decider_policeman": [
        [7.51, 0.6, 0.3, 1],
        [13.63, 0.6, 0.3, 0.8],
        [13.63, 0, 0, 0],
        [13.63, 110, 55, 220],
        [17.2, 10, 5, 20],
        [17.2, 0.6, 0.3, 1.2],
        [17.2, 0.6, 0.3, 1.5],
    ],
    "decider_economist": [
        [17.38, 0.5, 0.25, 1],
        [29.4, 0.6, 0.3, 1.2],
        [6.16, 0.3, 0.15, 0.6],
        [6.16, 99, 45, 180],
        [6.16, 6, 3, 12],
        [17.38, 0.5, 0.25, 1],
        [17.38, 0.5, 0.25, 1],
    ],
    "decider_environmental representative": [
        [4.96, 0.7, 0.35, 1.4],
        [7.08, 0.7, 0.35, 1.4],
        [17.31, 0.6, 0.3, 1.2],
        [18.93, 100, 50, 200],
        [18.93, 8, 4, 16],
        [17.52, 1, 0.5, 2],
        [15.27, 0.7, 0.35, 1.4],
    ],
    "decider_public representative": [
        [6.15, 0.4, 0.2, 0.8],
        [19.57, 0.4, 0.2, 0.8],
        [13.79, 0.2, 0.1, 0.4],
        [13.79, 60, 30, 120],
        [13.79, 4, 2, 8],
        [16.45, 0.6, 0.15, 0.6],
        [16.45, 0.4, 0.2, 0.8],
    ],
}

# Fixed list of criteria names for display
CRITERIA_NAMES = ["Nuisances", "Noise", "Impacts", "Geotechnics", "Equipment", "Accessibility", "Climate"]


def _to_float_safe(x):
    """Convert to float, handling comma decimals."""
    if x is None:
        raise ValueError("None")
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s.count(",") == 1 and s.count(".") == 0:
        s2 = s.replace(",", ".")
    else:
        s2 = s.replace(" ", "").replace(",", ".")
    allowed = "0123456789.-+eE"
    s3 = "".join(ch for ch in s2 if ch in allowed)
    if s3 == "" or s3 in {".", "-", "+", "+.", "-."}:
        raise ValueError(f"cannot parse '{x}' to float")
    return float(s3)


class PrometheeCalculator:
    """Lightweight PROMETHEE II calculator."""
    def __init__(self, perf, weights, P_list, Q_list):
        self.perf = np.array(perf, dtype=float)
        self.n, self.m = self.perf.shape
        self.weights = np.array(weights, dtype=float)
        self.P = np.array(P_list, dtype=float)
        self.Q = np.array(Q_list, dtype=float)
        self.wsum = float(np.sum(self.weights)) if self.weights.size > 0 else 1.0

    def _pi_linear(self, d, Pk, Qk):
        if Pk == Qk:
            return np.where(d > Pk, 1.0, 0.0)
        res = np.zeros_like(d, dtype=float)
        mask_mid = (d > Qk) & (d < Pk)
        res[mask_mid] = (d[mask_mid] - Qk) / (Pk - Qk)
        res[d >= Pk] = 1.0
        return res

    def compute_action_action_matrix(self):
        n = self.n
        Pi = np.zeros((n, n), dtype=float)
        for k in range(self.m):
            fk = self.perf[:, k]
            Pk = self.P[k]
            Qk = self.Q[k]
            wk = self.weights[k]
            d = fk.reshape((n, 1)) - fk.reshape((1, n))
            pi_k = self._pi_linear(d, Pk, Qk)
            Pi += wk * pi_k
        if self.wsum != 0:
            Pi = Pi / self.wsum
        return Pi

    def compute_flows_and_ranking(self, Pi):
        n = Pi.shape[0]
        phi_plus = np.sum(Pi, axis=1) / (n - 1)
        phi_minus = np.sum(Pi, axis=0) / (n - 1)
        phi = phi_plus - phi_minus
        ranking_idx = np.argsort(-phi)  # descending
        return phi_plus, phi_minus, phi, ranking_idx


class DeciderApp:
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.root.title(f"DECIDER - {name}")
        self.root.geometry("750x520")

        top = ttk.Frame(root)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text=f"Decider: {name}", font=("Arial", 14, "bold")).pack(side="left")

        self.status = ttk.Label(root, text="⏳ Waiting for coordinator...", foreground="gray")
        self.status.pack(fill="x", padx=8, pady=4)

        # Treeview for matrix display
        self.tree = ttk.Treeview(root, show="headings")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        # Buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=6)
        self.pref_btn = ttk.Button(btn_frame, text="Show Preferences", command=self.show_preferences, state="disabled")
        self.pref_btn.pack(side="left", padx=4)
        self.promethee_btn = ttk.Button(btn_frame, text="PROMETHEE", command=self.run_promethee, state="disabled")
        self.promethee_btn.pack(side="left", padx=4)
        
        # Bouton Négociation - toujours activé
        self.neg_btn = ttk.Button(btn_frame, text="🤝 Start Negotiation", 
                                  command=self.open_neg_window, state="normal")
        self.neg_btn.pack(side="left", padx=4)

        # SocketIO client
        self.sio = None
        self.sio_thread = None
        
        # Internal storage
        self.actions = []
        self.criteria_headers = []
        self.performance_matrix = None
        self.promethee_results = None
        
        # Négociation
        self.neg_window = None
        self.current_action = None
        self.neg_label = None
        self.accept_btn = None
        self.decline_btn = None
        
        self.start_socketio_client()

    def start_socketio_client(self):
        def run_client():
            try:
                self.sio = socketio.Client(logger=False, reconnection=True)

                @self.sio.on("matrix_update")
                def on_matrix_update(data):
                    matrix = data.get("matrix")
                    if matrix:
                        self.root.after(0, lambda: self._show_matrix(matrix))

                @self.sio.on("negotiation_proposal")
                def on_negotiation_proposal(data):
                    action = data.get("action")
                    if action:
                        self.root.after(0, lambda: self._handle_proposal(action))

                @self.sio.on("negotiation_selected")
                def on_negotiation_selected(data):
                    action = data.get("action")
                    self.root.after(0, lambda: self._handle_selected(action))

                @self.sio.event
                def connect():
                    print(f"✅ {self.name} connected to server")
                    self.root.after(0, lambda: self.status.config(text=f"✅ Connected as {self.name}"))

                @self.sio.event
                def disconnect():
                    self.root.after(0, lambda: self.status.config(text="🔴 Disconnected"))

                # Connect with name parameter
                self.sio.connect(f"{SERVER_WS}?name={self.name}")
                self.sio.wait()
            except Exception as e:
                self.root.after(0, lambda err=e: self.status.config(text=f"❌ Connection error: {str(err)[:50]}"))

        self.sio_thread = threading.Thread(target=run_client, daemon=True)
        self.sio_thread.start()

    def _log(self, msg):
        self.status.config(text=msg)

    def _show_matrix(self, matrix):
        """Display the received matrix."""
        for c in self.tree.get_children():
            self.tree.delete(c)
        
        if not matrix or not matrix[0]:
            return
        
        num_cols = len(matrix[0])
        cols = [f"col{i}" for i in range(num_cols)]
        self.tree["columns"] = cols
        
        header_row = matrix[0]
        for idx, col_id in enumerate(cols):
            heading = header_row[idx] if idx < len(header_row) else f"Col {idx+1}"
            self.tree.heading(col_id, text=str(heading))
            self.tree.column(col_id, width=110, anchor="center")

        for row in matrix[1:]:
            row_display = [row[i] if i < len(row) else "" for i in range(num_cols)]
            self.tree.insert("", "end", values=row_display)

        # Parse numeric data
        actions = []
        criteria_headers = header_row[1:]
        numeric_rows = []
        
        for r in matrix[1:]:
            if not r:
                continue
            action_name = str(r[0]) if len(r) > 0 else ""
            actions.append(action_name)
            numeric_cells = []
            for cell in r[1:]:
                try:
                    val = _to_float_safe(cell)
                    numeric_cells.append(val)
                except Exception:
                    numeric_cells.append(float("nan"))
            numeric_rows.append(numeric_cells)

        if numeric_rows:
            max_len = max(len(r) for r in numeric_rows)
            padded = [r + [float("nan")] * (max_len - len(r)) for r in numeric_rows]
            perf = np.array(padded, dtype=float)
            expected_m = len(CRITERIA_NAMES)
            if perf.shape[1] >= expected_m:
                perf = perf[:, :expected_m]
                criteria_headers = criteria_headers[:expected_m]
            
            self.actions = actions
            self.criteria_headers = criteria_headers
            self.performance_matrix = perf
            self._log(f"✅ Matrix received ({perf.shape[0]} actions x {perf.shape[1]} criteria)")
        else:
            self.performance_matrix = None
            self.actions = []
            self.criteria_headers = []
            self._log("⚠️ No numeric data found")

        self.pref_btn.config(state="normal")
        self.promethee_btn.config(state="normal")

    def _handle_proposal(self, action):
        """Handle action proposal from coordinator."""
        self.current_action = action
        
        # Open negotiation window if not already open
        if not self.neg_window or not self.neg_window.winfo_exists():
            self.open_neg_window()
        
        # Calculate action rank
        action_rank = None
        rank_text = ""
        rank_color = "black"
        
        if self.promethee_results and self.actions:
            try:
                action_index = self.actions.index(action)
                ranking = self.promethee_results["ranking_idx"]
                # Find the rank (1-based index)
                rank_position = np.where(ranking == action_index)[0]
                if len(rank_position) > 0:
                    action_rank = rank_position[0] + 1  # +1 for 1-based ranking
                    
                    # Color code based on rank
                    if action_rank <= 13:
                        rank_color = "green"
                    else:
                        rank_color = "red"
                        
                    rank_text = f"Rank: {action_rank} / {len(self.actions)}"
                else:
                    rank_text = "Rank: Not ranked"
                    rank_color = "gray"
            except ValueError:
                rank_text = "Rank: Action not found"
                rank_color = "gray"
        else:
            rank_text = "Rank: No ranking available"
            rank_color = "gray"
        
        # Check if action is in top 13 of ranking
        is_top13 = action_rank is not None and action_rank <= 13
    
        # Update UI
        if self.neg_label:
            self.neg_label.config(text=f"Proposed Action: {action}")
        
        if hasattr(self, 'rank_label') and self.rank_label:
            self.rank_label.config(text=rank_text, foreground=rank_color)
        
        # Enable/disable buttons
        if self.accept_btn and self.decline_btn:
            if is_top13:
                btn_text = f"✅ Accept (Rank #{action_rank})"
                self.accept_btn.config(state="normal", text=btn_text)
            else:
                if action_rank:
                    btn_text = f"❌ Rank #{action_rank} (not top 13)"
                else:
                    btn_text = "❌ Not in top 13"
                self.accept_btn.config(state="disabled", text=btn_text)
            self.decline_btn.config(state="normal")
        
        # Show message
        messagebox.showinfo("Negotiation Proposal", 
                        f"Action proposed: {action}\n\n"
                        f"{rank_text}\n"
                        f"This action is {'in' if is_top13 else 'NOT in'} your top 13 ranking.")
    
    def open_neg_window(self):
        """Open negotiation window."""
        if self.neg_window and self.neg_window.winfo_exists():
            self.neg_window.lift()
            return
        
        self.neg_window = tk.Toplevel(self.root)
        self.neg_window.title(f"Negotiation - {self.name}")
        self.neg_window.geometry("400x350")
        
        # Titre
        ttk.Label(self.neg_window, text="🤝 NEGOTIATION", 
                font=("Arial", 14, "bold")).pack(pady=10)
        
        # Status label - Action
        self.neg_label = ttk.Label(self.neg_window, text="Waiting for proposal...", 
                                font=("Arial", 11))
        self.neg_label.pack(pady=5)
        
        # Rank label
        self.rank_label = ttk.Label(self.neg_window, text="", 
                                font=("Arial", 10, "bold"),
                                foreground="blue")
        self.rank_label.pack(pady=5)
        
        # Instructions
        ttk.Label(self.neg_window, 
                text="Rules:\n• Accept if action is in your top 13 ranking\n• Decline otherwise", 
                font=("Arial", 9), foreground="gray").pack(pady=5)
        
        # Button frame
        btn_frame = ttk.Frame(self.neg_window)
        btn_frame.pack(pady=20)
        
        self.accept_btn = ttk.Button(btn_frame, text="✅ Accept", 
                                    command=self.accept_action, 
                                    state="disabled", width=18)
        self.accept_btn.pack(side="left", padx=10)
        
        self.decline_btn = ttk.Button(btn_frame, text="❌ Decline", 
                                    command=self.decline_action, 
                                    state="disabled", width=18)
        self.decline_btn.pack(side="left", padx=10)
        
        # Close button
        ttk.Button(self.neg_window, text="Close", 
                command=self.neg_window.destroy).pack(pady=10)
        
        # If there's already a current action, update UI
        if self.current_action:
            self._handle_proposal(self.current_action)

    def accept_action(self):
        """Send accept response."""
        if self.current_action and self.sio:
            try:
                self.sio.emit("negotiation_response", {
                    "decider": self.name,
                    "action": self.current_action,
                    "answer": "accept"
                })
                self.neg_label.config(text=f"✅ You accepted: {self.current_action}")
                self.accept_btn.config(state="disabled")
                self.decline_btn.config(state="disabled")
                print(f"{self.name} accepted {self.current_action}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send response: {e}")

    def decline_action(self):
        """Send decline response."""
        if self.current_action and self.sio:
            try:
                self.sio.emit("negotiation_response", {
                    "decider": self.name,
                    "action": self.current_action,
                    "answer": "decline"
                })
                self.neg_label.config(text=f"❌ You declined: {self.current_action}")
                self.accept_btn.config(state="disabled")
                self.decline_btn.config(state="disabled")
                print(f"{self.name} declined {self.current_action}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send response: {e}")

    def show_preferences(self):
        prefs = DECIDER_PREFS.get(self.name.lower())
        if not prefs:
            messagebox.showerror("Error", f"No preferences found for {self.name}")
            return

        pref_window = tk.Toplevel(self.root)
        pref_window.title(f"{self.name}'s Preferences")
        pref_window.geometry("600x320")
        ttk.Label(pref_window, text=f"Subjective parameters of {self.name}", 
                 font=("Arial", 12, "bold")).pack(pady=8)

        cols = ["Criteria", "Weight", "P", "Q", "V"]
        tree = ttk.Treeview(pref_window, columns=cols, show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center", width=100)
        tree.pack(padx=10, pady=10, fill="both", expand=True)

        for crit_name, vals in zip(CRITERIA_NAMES, prefs):
            tree.insert("", "end", values=[crit_name] + vals)

        ttk.Button(pref_window, text="Close", command=pref_window.destroy).pack(pady=8)

    def run_promethee(self):
        if self.performance_matrix is None:
            messagebox.showwarning("Warning", "No numeric data available for PROMETHEE calculation.")
            return

        prefs = DECIDER_PREFS.get(self.name.lower())
        if not prefs:
            messagebox.showerror("Error", f"No preferences found for {self.name}")
            return

        m_available = min(self.performance_matrix.shape[1], len(prefs))
        weights = [prefs[i][0] for i in range(m_available)]
        P_list = [prefs[i][1] for i in range(m_available)]
        Q_list = [prefs[i][2] for i in range(m_available)]

        calc = PrometheeCalculator(self.performance_matrix[:, :m_available], weights, P_list, Q_list)
        Pi = calc.compute_action_action_matrix()
        phi_plus, phi_minus, phi, ranking_idx = calc.compute_flows_and_ranking(Pi)

        self.promethee_results = {
            "Pi": Pi,
            "phi_plus": phi_plus,
            "phi_minus": phi_minus,
            "phi": phi,
            "ranking_idx": ranking_idx,
        }

        win = tk.Toplevel(self.root)
        win.title(f"PROMETHEE - {self.name}")
        win.geometry("360x220")
        ttk.Label(win, text=f"{self.name} — PROMETHEE results", 
                 font=("Arial", 12, "bold")).pack(pady=8)

        ttk.Button(win, text="Agrégation (Action–Action matrix)", 
                  command=self._show_pi_window).pack(pady=6, fill="x", padx=12)
        ttk.Button(win, text="Exploitation (Flows)", 
                  command=self._show_flows_window).pack(pady=6, fill="x", padx=12)
        ttk.Button(win, text="Rangement final (Ranking)", 
                  command=self._show_ranking_window).pack(pady=6, fill="x", padx=12)

    def _show_pi_window(self):
        Pi = self.promethee_results["Pi"]
        n = Pi.shape[0]
        win = tk.Toplevel(self.root)
        win.title("Action–Action matrix (Pi)")
        win.geometry("900x500")

        txt = tk.Text(win, wrap="none")
        txt.pack(expand=True, fill="both")
        header = "\t" + "\t".join(self.actions) + "\n"
        txt.insert("end", header)
        for i in range(n):
            row_str = self.actions[i] + "\t" + "\t".join(f"{Pi[i,j]:.4f}" for j in range(n)) + "\n"
            txt.insert("end", row_str)

    def _show_flows_window(self):
        phi_plus = self.promethee_results["phi_plus"]
        phi_minus = self.promethee_results["phi_minus"]
        phi = self.promethee_results["phi"]
        n = len(phi)
        win = tk.Toplevel(self.root)
        win.title("Flows (Phi+, Phi-, Phi)")
        win.geometry("600x420")

        txt = tk.Text(win, wrap="none")
        txt.pack(expand=True, fill="both")
        txt.insert("end", "Action\tPhi+\tPhi-\tPhi\n")
        for i in range(n):
            txt.insert("end", f"{self.actions[i]}\t{phi_plus[i]:.4f}\t{phi_minus[i]:.4f}\t{phi[i]:.4f}\n")

    def _show_ranking_window(self):
        phi = self.promethee_results["phi"]
        ranking_idx = self.promethee_results["ranking_idx"]
        win = tk.Toplevel(self.root)
        win.title("Final Ranking")
        win.geometry("500x450")

        content_frame = ttk.Frame(win)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        txt = tk.Text(content_frame, wrap="none")
        txt.pack(expand=True, fill="both")
        txt.insert("end", "Rank\tAction\tPhi\n")
        for rank, idx in enumerate(ranking_idx, start=1):
            txt.insert("end", f"{rank}\t{self.actions[idx]}\t{phi[idx]:.4f}\n")

        send_btn_frame = ttk.Frame(win)
        send_btn_frame.pack(fill="x", padx=10, pady=10)
        send_btn = ttk.Button(send_btn_frame, text="🚀 Send Ranking to Coordinator", 
                             command=lambda: self._send_final_result(phi, ranking_idx))
        send_btn.pack()

    def _send_final_result(self, phi, ranking_idx):
        """Send final ranking to coordinator."""
        try:
            ranking_list = [int(i) for i in ranking_idx]
            payload = {
                "decider": self.name,
                "phi": phi.tolist(),
                "ranking": ranking_list
            }
            self.sio.emit("final_ranking", payload)
            messagebox.showinfo("Success", "Final ranking sent to coordinator! 🎉")
            self._log("✅ Ranking sent to coordinator")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot send result: {e}")


if __name__ == "__main__":
    # Get decider name from command line or use default
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        # Show dialog to select decider
        root_temp = tk.Tk()
        root_temp.withdraw()
        
        from tkinter import simpledialog
        available_deciders = list(DECIDER_PREFS.keys())
        name = simpledialog.askstring("Decider Selection", 
                                     "Enter decider name:", 
                                     initialvalue=available_deciders[0])
        root_temp.destroy()
        
        if not name:
            print("No decider name provided. Exiting.")
            sys.exit(1)
    
    root = tk.Tk()
    app = DeciderApp(root, name)
    root.mainloop()